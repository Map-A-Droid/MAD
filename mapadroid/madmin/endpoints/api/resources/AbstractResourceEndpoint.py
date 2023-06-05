from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Set

import pymysql as pymysql
from aiohttp import web
from loguru import logger
from sqlalchemy import Column
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.properties import ColumnProperty
from yarl import URL

from mapadroid.db.model import AuthLevel, Base
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)


class DataHandlingMethodology(Enum):
    CREATE = "post",
    REPLACE = "put",
    UPDATE = "patch"


class AbstractResourceEndpoint(AbstractMadminRootEndpoint, ABC):
    # TODO: '%s/<string:identifier>' optionally at the end of the route
    # TODO: ResourceEndpoint class that loads the identifier accordingly before patch/post etc are called (populate_mode)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def post(self) -> web.Response:
        api_request_data = await self.request.json()
        return await self._update_or_create_object(None, api_request_data,
                                                   methodology=DataHandlingMethodology.CREATE)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def patch(self) -> web.Response:
        identifier = self.request.match_info.get('identifier', None)
        if not identifier:
            return await self._json_response(self.request.method, status=405)
        api_request_data = await self.request.json()
        return await self._update_or_create_object(identifier, api_request_data,
                                                   methodology=DataHandlingMethodology.UPDATE)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def delete(self) -> web.Response:
        identifier = self.request.match_info.get('identifier', None)
        if not identifier:
            return await self._json_response(self.request.method, status=405)
        db_entry: Optional[Base] = await self._fetch_from_db(identifier)
        if not db_entry:
            return await self._json_response(self.request.method, status=404)
        # Check dependencies. If there are any, we need to abort and return a proper response
        unmet_dependencies: Optional[Dict[int, str]] = await self._get_unmet_dependencies(db_entry)
        if unmet_dependencies:
            logger.warning("Unmet dependencies for {}: {}", db_entry, unmet_dependencies)
            formatted: List[Dict] = [{"uri": elem_id, "name": name} for elem_id, name in unmet_dependencies.items()]
            return await self._json_response(formatted, status=412)
        try:
            await self._delete_connected_prior(db_entry)
        except pymysql.err.IntegrityError as e:
            logger.warning("Failed deleting connected prio to deleting the main item. {}", e)
        await self._delete(db_entry)
        try:
            await self._delete_connected_post(db_entry)
        except pymysql.err.IntegrityError as e:
            logger.warning("Failed deleting connected after deleting the main item. {}", e)
        headers = {
            'X-Status': 'Successfully deleted the object'
        }
        return await self._json_response(None, status=202, headers=headers)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self) -> web.Response:
        result: Dict = {}
        identifier = self.request.match_info.get('identifier', None)
        # TODO: Both fetch all and fetch from DB need to be translated for response with uris for foreign keys.
        # TODO: "results" needs to be a Dict[uris, objects]
        found_entries: Dict[int, Base] = {}
        if not identifier:
            found_entries: Dict[int, Base] = await self._fetch_all_from_db()
        else:
            entry: Optional[Base] = await self._fetch_from_db(identifier)
            if not entry:
                return await self._json_response(self.request.method, status=404)
            else:
                found_entries[identifier] = entry
        for identifier, value in found_entries.items():
            if isinstance(value, list):
                # hopefully a plain list...
                found_entries[identifier] = value
            else:
                found_entries[identifier] = self._translate_object_for_response(value)
                additional_keys: Dict = await self._get_additional_keys(identifier)
                for key, key_value in additional_keys.items():  # TODO: Recursive...
                    if isinstance(key_value, Base):
                        additional_keys[key] = self._translate_object_for_response(key_value)
                    elif isinstance(key_value, list) and all(isinstance(x, Base) for x in key_value):
                        additional_keys[key] = [self._translate_object_for_response(x) for x in key_value]

                found_entries[identifier].update(additional_keys)
        result["results"] = found_entries
        if self.request.query.get("hide_resource", "0") == "0":
            # Include the resource info as it's not to be hidden...
            result["resource"] = self._resource_info()
        return await self._json_response(data=result)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def put(self) -> web.Response:
        identifier = self.request.match_info.get('identifier', None)
        if not identifier:
            return await self._json_response(self.request.method, status=405)
        api_request_data = await self.request.json()
        return await self._update_or_create_object(identifier, api_request_data,
                                                   methodology=DataHandlingMethodology.REPLACE)

    async def _update_or_create_object(self, identifier: Optional[int], api_request_data: Dict,
                                       methodology: DataHandlingMethodology) -> web.Response:
        try:
            # TODO: REPLACE needs to REPLACE the entire obj -> Delete and then create it from scratch...
            #  aka: ensure creating a new instance works
            if identifier:
                db_entry: Optional[Base] = await self._fetch_from_db(identifier)
            else:
                db_entry: Optional[Base] = None
            if not db_entry and methodology in (DataHandlingMethodology.CREATE, DataHandlingMethodology.REPLACE):
                # Try to create an area if possible...
                db_entry = await self._create_instance(identifier)
            elif not db_entry and methodology in DataHandlingMethodology.UPDATE:
                return await self._json_response("DB entry with ID {} could not be found.".format(str(identifier)),
                                                 status=404)
            elif not db_entry:
                return await self._json_response("DB entry with ID {} could not be created.".format(str(identifier)),
                                                 status=405)
            type_of_obj = type(db_entry)
            vars_of_type = vars(type_of_obj)

            missing: List[str] = []
            # first validate if any fields are missing...
            for variable, type_info in vars_of_type.items():
                # TODO: Also do not continue if FK?
                if variable in self._attributes_to_ignore():
                    continue
                type_of_var = vars_of_type.get(variable)
                if (isinstance(type_of_var, InstrumentedAttribute) and type_of_var.is_attribute
                        and isinstance(type_of_var.prop, ColumnProperty)
                        and not type_of_var.nullable
                        and type_of_var.comparator.autoincrement is not True):
                    # variable is needed (PK or not nullable)
                    to_be_set = api_request_data.get(variable)
                    if to_be_set is None and getattr(db_entry, variable, None) is None:
                        missing.append(variable)
            if missing:
                logger.error("Missing fields: {}", missing)
                self._commit_trigger = False
                return await self._json_response({"missing": missing},
                                                 status=405)
            handled: Set[str] = set()
            for key, value in api_request_data.items():
                if key in self._attributes_to_ignore() or key.startswith("_") or key not in vars_of_type:
                    continue
                elif vars_of_type.get(key) and not isinstance(vars_of_type.get(key), InstrumentedAttribute):
                    # We only allow modifying columns ;)
                    continue
                elif await self._handle_additional_keys(db_entry, key, value):
                    handled.add(key)
                    continue
                # validate whether a field is required...
                elif ((getattr(vars_of_type.get(key), "primary_key", None)
                       or not getattr(vars_of_type.get(key), "primary_key", None))
                      and getattr(db_entry, key, None) is None and value is None):
                    self._commit_trigger = False
                    return await self._json_response({"missing": [key]},
                                                     status=405)
                # TODO: Support "legacy" translations of fields? e.g. origin -> name
                if isinstance(value, str) and value.lower() in ["none", "undefined"]:
                    value = None
                elif isinstance(value, bool) or isinstance(value, str) and value.lower() in ["true", "false"]:
                    if isinstance(value, str):
                        value = 1 if value.lower() == "true" else 0
                    else:
                        value = 1 if value else 0
                setattr(db_entry, key, value)
            self._session.add(db_entry)
            await self._session.commit()
            await self._session.refresh(db_entry)
            for key, value in api_request_data.items():
                if key not in handled:
                    await self._handle_additional_keys(db_entry, key, value)
            self._save(db_entry)
        except Exception as err:
            self._commit_trigger = False
            logger.exception(err)
            return await self._json_response(str(err), status=400)

        headers = {
            'Location': str(identifier),
            'X-Uri': str(self.request.url),
            'X-Status': 'Successfully created the object'
        }

        if methodology in (DataHandlingMethodology.CREATE, DataHandlingMethodology.REPLACE):
            headers["X-Status"] = 'Successfully created the object'
            return await self._json_response({}, status=201, headers=headers)
        else:
            headers["X-Status"] = 'Successfully updated the object'
            return await self._json_response({}, status=204, headers=headers)

    # TODO: lateron: Derive resource_def from model class.
    #  Column nullable=False => required=True
    #  Foreign Key => URI to be built using a lookup of Dict[ModelClass, str]
    #  If nullable=True (not present basically) and foreign key => "empty"=None
    #  If nullable=False and foreign key
    #  Set containing columns to be hidden?
    # for now:
    #  parse resource def for URIs and set the key to the according resource URI
    def _translate_object_for_response(self, obj: Base) -> Dict:
        translated: Dict = {}
        obj_vars = vars(obj)
        type_of_obj = type(obj)
        vars_of_type = vars(type_of_obj)
        for attr, value in obj_vars.items():
            attribute_type = vars_of_type.get(attr)
            if attribute_type and isinstance(attribute_type, InstrumentedAttribute):
                if len(attribute_type.foreign_keys) > 0:
                    # Foreign key field, we need to construct the matching API call...
                    # TODO: is ".path" correct?
                    uri = self._api_uri_for_column(obj, attr, value)
                    if not uri:
                        translated[attr] = value
                    else:
                        translated[attr] = uri.path
                else:
                    translated[attr] = value
        return translated

    def _api_uri_for_column(self, obj: Base, key: str, col: Column) -> Optional[URL]:
        resource_def: Dict = self._resource_info(obj)
        fields: Dict = resource_def.get("fields", {})
        settings_of_attr: Optional[Dict] = None
        if key in fields:
            settings_of_attr: Optional[Dict] = fields.get(key)
        if not settings_of_attr:
            return None
        settings_of_attr = settings_of_attr.get("settings", {})
        uri: Optional[bool] = settings_of_attr.get("uri")
        if not uri:
            return None
        else:
            uri_source = settings_of_attr.get("uri_source")
            router = self.request.app.router.get(uri_source)
            if not router:
                return None
            return self._url_for(uri_source, dynamic_path={"identifier": col})
            # return router.url_for(identifier=col)

    @abstractmethod
    def _attributes_to_ignore(self) -> Set[str]:
        """

        Returns: Set containing keys that should not be updated as is. E.g. the identifier.

        """
        pass

    # TODO: Fetch & create should accept kwargs for primary keys consisting of multiple columns
    @abstractmethod
    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        """

        Args:
            identifier:
            **kwargs:

        Returns: Fetches the entry from DB using the given identifier. None if not found.

        """
        pass

    @abstractmethod
    async def _create_instance(self, identifier) -> Base:
        """

        Args:
            identifier: may be optional in case of autoincrement. However, replace requires it

        Returns: Instantiates the type of resource that the endpoint is supposed to handle as such that it fills the
        bare minimum of data (instance_id and identifier...)

        """
        pass

    @abstractmethod
    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        """

        Args:
            **kwargs:

        Returns: All entries in the DB that match the type and criteria implemented in the specific endpoints. Keys are
        identifiers of the entries, values are the actual entries

        """
        pass

    @abstractmethod
    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        """

        Returns: The resource def of the data_manager like dictionary containing fields and settings with their types etc

        """
        pass

    async def _get_additional_keys(self, identifier: int) -> Dict:
        """
        Method that can optionally be overwritten to add returning certain keys and
        values within an object's dict
        Args:
            identifier:

        Returns:

        """
        return {}

    async def _handle_additional_keys(self, db_entry: Base, key: str, value) -> bool:
        """
        Allows the update/setter to handle additional keys such as mon IV lists that
        are stored in another table
        Args:
            db_entry:
            key:
            value:

        Returns: True if key was handled, False otherwise

        """
        return False

    async def _check_dependencies_met(self, db_entry) -> bool:
        """

        Args:
            db_entry:

        Returns: True if dependencies are met, i.e. no nullable=False columns will be violated after deletion that
        are not to be handled automatically. For example, deleting a walker shall be disallowed unless there are no
        devices assigned to it.

        """
        return True

    @abstractmethod
    async def _delete_connected_prior(self, db_entry):
        pass

    @abstractmethod
    async def _delete_connected_post(self, db_entry):
        pass

    async def _get_unmet_dependencies(self, db_entry) -> Optional[Dict[int, str]]:
        """

        Args:
            db_entry:

        Returns: Dict of ID, human-readable strings if dependencies have not been met,, i.e. nullable=False columns will
        be violated after deletion that are not to be handled automatically. For example, deleting a walker shall be
        disallowed unless there are no
        devices assigned to it.

        """
        return None
