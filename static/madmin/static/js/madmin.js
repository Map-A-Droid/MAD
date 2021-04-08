let locInjectPane = null;
let locInjectBtn = L.easyButton({
    position: "bottomright",
    states: [{
        stateName: "scanmode-activate",
        icon: "fa-satellite-dish",
        title: "Enable click-to-scan mode",
        onClick: function (btn, map) {
            clickToScanActive = true;
            L.DomUtil.addClass(map._container, "crosshair-cursor-enabled");
            locInjectPane = map.createPane("locinject")
            locInjectPane.style.pointerEvents = "auto";
            btn.state("scanmode-deactivate");
        }
    }, {
        stateName: "scanmode-deactivate",
        icon: "fa-satellite-dish",
        title: "Disable click-to-scan mode",
        onClick: function (btn, map) {
            clickToScanActive = false;
            L.DomUtil.removeClass(map._container, "crosshair-cursor-enabled");
            L.DomUtil.remove(locInjectPane);
            btn.state("scanmode-activate");
        }
    }]
});

function copyClipboard(text) {
    navigator.clipboard.writeText(text.replace("|", ",")).then(function () {
        alert('Copying to clipboard was successful!');
    }, function (err) {
        alert('Could not copy text: ', err);
    });
};

$(document).on("hidden.bs.modal", "#injectionModal", function (e) {
    locInjectBtn.state("scanmode-activate");
    clickToScanActive = false;
    L.DomUtil.removeClass(map._container, 'crosshair-cursor-enabled');
    L.DomUtil.remove(locInjectPane);
});

$(document).on("click", "#sendworker", function () {
    var location = $(this).attr("data-loc");
    $('#injectLocation').val(location);
    $('#injectionModal').modal();
});

L.Marker.addInitHook(function () {
    if (this.options.virtual) {
        this.on('add', function () {
            this._updateIconVisibility = function () {
                if (!this._map) {
                    return;
                }
                var map = this._map;
                var isVisible = map.getBounds().contains(this.getLatLng());
                var wasVisible = this._wasVisible;
                var icon = this._icon;
                var iconParent = this._iconParent;
                var shadow = this._shadow;
                var shadowParent = this._shadowParent;

                if (!iconParent) {
                    iconParent = this._iconParent = icon.parentNode;
                }
                if (shadow && !shadowParent) {
                    shadowParent = this._shadowParent = shadow.parentNode;
                }

                if (isVisible != wasVisible) {
                    if (isVisible) {
                        iconParent.appendChild(icon);
                        if (shadow) {
                            shadowParent.appendChild(shadow);
                        }
                    } else {
                        iconParent.removeChild(icon);
                        if (shadow) {
                            shadowParent.removeChild(shadow);
                        }
                    }

                    this._wasVisible = isVisible;

                }
            };

            this._map.on('resize moveend zoomend', this._updateIconVisibility, this);
            this._updateIconVisibility();

        }, this);
    }
});

// fix gaps in tile rendering
(function () {
    var originalInitTile = L.GridLayer.prototype._initTile
    L.GridLayer.include({
        _initTile: function (tile) {
            originalInitTile.call(this, tile);

            var tileSize = this.getTileSize();

            tile.style.width = tileSize.x + 1 + 'px';
            tile.style.height = tileSize.y + 1 + 'px';
        }
    });
})()

// globals
let map;
let mapEventForwarder;
let sidebar;
let init = true;
let fetchTimeout = null;
let clickToScanActive = false;
let cleanupInterval = null;
const teamNames = ["Uncontested", "Mystic", "Valor", "Instinct"];
const iconBasePath = "https://raw.githubusercontent.com/whitewillem/PogoAssets/resized/icons_large";

// pane (and order inside that pane) of various layers
const layerOrders = {
    cells: { pane: "cells" },
    areas: { pane: "fences", bringTo: "bringToBack" },
    geofences: { pane: "fences", bringTo: "bringToFront" },
    routes: { pane: "routes" },
    gyms: { pane: "points", bringTo: "bringToBack" },
    stops: { pane: "points", bringTo: "bringToBack" },
    spawns: { pane: "points" },
    raids: { pane: "markers" },
    quests: { pane: "markers" },
    mons: { pane: "markers" },
    workers: { pane: "markers", bringTo: "bringToFront" }
};

// object to hold all the markers and elements
const leaflet_data = {
    tileLayer: "",
    raids: {},
    spawns: {},
    quests: {},
    gyms: {},
    routes: {},
    prioroutes: {},
    geofences: {},
    areas: {},
    workers: {},
    mons: {},
    monicons: {},
    cellupdates: {},
    stops: {}
};

const mouseEventsIgnore = {
    ignoreCount: 0,
    enableIgnore() {
        ++this.ignoreCount;
        mapEventForwarder.isEnabled = false;
    },
    disableIgnore() {
        if (--this.ignoreCount === 0) {
            mapEventForwarder.isEnabled = true;
        }
    },
    isIgnored() {
        return this.ignoreCount !== 0;
    }
}

new Vue({
    el: '#app',
    data: {
        raids: {},
        gyms: {},
        quests: {},
        stops: {},
        mons: {},
        spawns: {},
        cellupdates: {},
        fetchers: {},
        layers: {
            stat: {
                gyms: false,
                quests: false,
                stops: false,
                workers: false,
                mons: false,
                cellupdates: false
            },
            dyn: {
                routes: {},
                prioroutes: {},
                geofences: {},
                areas: {},
                spawns: {}
            }
        },
        workers: {},
        maptiles: {
            cartodblight: {
                name: "CartoDB Positron",
                url: "https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png"
            },
            cartodblightnolabel: {
                name: "CartoDB Positron nolabel",
                url: "https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}.png"
            },
            cartodbdark: {
                name: "CartoDB Darkmatter",
                url: "https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png"
            },
            cartodbdarknolabel: {
                name: "CartoDB Darkmatter nolabel",
                url: "https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}.png"
            },
            cartodbvoyager: {
                name: "CartoDB Voyager",
                url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            },
            osm: {
                name: "OpenStreetMap",
                url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            },
            osmhot: {
                name: "OpenStreetMap HOT",
                url: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
            },
            hydda: {
                name: "Hydda",
                url: "https://{s}.tile.openstreetmap.se/hydda/full/{z}/{x}/{y}.png"
            }
        },
        settings: {
            cleanup: true,
            maptiles: "cartodblight",
            routes: {
                coordinateRadius: {
                    raids: 490,
                    quests: 40,
                    mons: 67
                }
            },
            cellUpdateTimeout: 50000
        }
    },
    computed: {
        sortedGeofences() {
            return Object.values(this.layers.dyn.geofences).sort(function (x, y) {
                return x.name.localeCompare(y.name, "en", {sensitivity: "base"});
            });
        },
        sortedRoutes() {
            return Object.values(this.layers.dyn.routes).sort(function (x, y) {
                return x.name.localeCompare(y.name, "en", {sensitivity: "base"});
            });
        }
    },
    watch: {
        "layers.stat.gyms": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_gyms(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("gyms", oldVal, newVal, layerOrders.gyms.bringTo);
            this.changeStaticLayer("raids", oldVal, newVal, layerOrders.raids.bringTo);
        },
        "layers.stat.workers": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_workers(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("workers", oldVal, newVal, layerOrders.workers.bringTo);
        },
        "layers.stat.quests": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_quests(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("quests", oldVal, newVal, layerOrders.quests.bringTo);
        },
        "layers.stat.stops": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_stops(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("stops", oldVal, newVal, layerOrders.stops.bringTo);
        },
        "layers.stat.mons": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_mons(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("mons", oldVal, newVal, layerOrders.mons.bringTo);
        },
        "layers.stat.cellupdates": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_cells(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("cellupdates", oldVal, newVal, layerOrders.cells.bringTo);
        },
        "layers.dyn.spawns": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("spawns", true, layerOrders.spawns.bringTo);
            }
        },
        "layers.dyn.geofences": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("geofences", false, layerOrders.geofences.bringTo);
            }
        },
        "layers.dyn.areas": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("areas", false, layerOrders.areas.bringTo);
            }
        },
        "layers.dyn.routes": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("routes", false, layerOrders.routes.bringTo);
            }
        },
        "layers.dyn.prioroutes": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("prioroutes", false, layerOrders.routes.bringTo);
            }
        },
        "settings.maptiles": function (newVal) {
            this.updateStoredSetting("settings-maptiles", newVal);
            leaflet_data.tileLayer.setUrl(this.maptiles[newVal].url);
        },
        "settings.cleanup": function (newVal) {
            this.updateStoredSetting("settings-cleanup", newVal);

            if (newVal) {
                this.cleanup();
            } else {
                clearInterval(cleanupInterval);
            }
        },
        "settings.cellUpdateTimeout": function (newVal) {
            this.updateStoredSetting('settings-cellUpdateTimeout', newVal);
        },
        "settings.routes.coordinateRadius": {
            deep: true,
            handler: function () {
                $this = this;
                for (routetype in this.settings.routes.coordinateRadius) {
                    this.updateStoredSetting('settings-coordinateRadius-' + routetype, this.settings.routes.coordinateRadius[routetype]);
                }

                for (route in leaflet_data["routes"]) {
                    leaflet_data["routes"][route].eachLayer(function (marker) {
                        try {
                            marker.setRadius($this.settings.routes.coordinateRadius[$this.layers.dyn.routes[route].mode]);
                        } catch (e) {
                            // routes have a special layer containing polylines
                            // unfortunately, there's no identifer for them, thus
                            // we catch this exception and ignore it
                        }
                    });
                }
            }
        }
    },
    mounted() {
        // reset some vars
        this.removeStoredSetting("fetchTimestamp");
        this.removeStoredSetting("oSwLat");
        this.removeStoredSetting("oSwLon");
        this.removeStoredSetting("oNeLat");
        this.removeStoredSetting("oNeLon");

        // init our map first
        this.initMap();
    },
    methods: {
        map_fetch_everything() {
            const urlFilter = this.buildUrlFilter();

            this.map_fetch_workers();
            this.map_fetch_gyms(urlFilter);
            this.map_fetch_routes();
            this.map_fetch_geofences();
            this.map_fetch_areas();
            this.map_fetch_spawns(urlFilter);
            this.map_fetch_quests(urlFilter);
            this.map_fetch_stops(urlFilter);
            this.map_fetch_mons(urlFilter);
            this.map_fetch_prioroutes();
            this.map_fetch_cells(urlFilter);

            this.updateBounds(true);
        },
        map_fetch_workers() {
            this.mapGuardedFetch("workers", "get_workers", function (res) {
                res.data.forEach(function (worker) {
                    const name = worker["name"];

                    if (this.workers[name]) {
                        leaflet_data.workers[name].setLatLng([worker["lat"], worker["lon"]])
                    }
                    else {
                        this.workers[name] = worker;

                        leaflet_data.workers[name] = L.circleMarker([worker["lat"], worker["lon"]], {
                            radius: 7,
                            color: "#E612CB",
                            fillColor: "#E612CB",
                            weight: 1,
                            opacity: 0.9,
                            fillOpacity: 0.9,
                            pane: layerOrders.workers.pane,
                            pmIgnore: true,
                        }).bindPopup(name);

                        this.addMouseEventPopup(leaflet_data.workers[name]);

                        if (this.layers.stat.workers) {
                            this.mapAddLayer(leaflet_data.workers[name], layerOrders.workers.bringTo);
                        }
                    }
                }, this);
            });
        },
        map_fetch_gyms(urlFilter) {
            if (!this.layers.stat.gyms) {
                return;
            }

            this.mapGuardedFetch("gyms", "get_gymcoords" + urlFilter, function (res) {
                res.data.forEach(function (gym) {

                    let color;
                    switch (gym["team_id"]) {
                        default:
                            color = "#888";
                            break;
                        case 1:
                            color = "#0C6DFF";
                            break;
                        case 2:
                            color = "#FC0016";
                            break;
                        case 3:
                            color = "#FD830E";
                            break;
                    }

                    const id = gym["id"];
                    let skip = true;

                    if (this.gyms[id]) {
                        // check if we should update an existing gym
                        if (this.gyms[id]["team_id"] !== gym["team_id"]) {
                            map.removeLayer(leaflet_data.gyms[id]);
                            delete leaflet_data.gyms[id];
                        }
                        else {
                            skip = false;
                        }
                    }

                    if (skip) {
                        // store gym meta data
                        this.gyms[id] = gym;

                        leaflet_data.gyms[id] = L.circle([gym["lat"], gym["lon"]], {
                            id: id,
                            radius: Math.pow((20 - map.getZoom()), 2.5),
                            color: color,
                            fillColor: color,
                            weight: 2,
                            opacity: 0.7,
                            fillOpacity: 0.7,
                            pane: layerOrders.gyms.pane,
                            pmIgnore: true
                        }).bindPopup(this.build_gym_popup, { "className": "gympopup", autoPan: false });

                        this.addMouseEventPopup(leaflet_data.gyms[id]);

                        // only add them if they're set to visible
                        if (this.layers.stat.gyms) {
                            this.mapAddLayer(leaflet_data.gyms[id], layerOrders.gyms.bringTo);
                        }
                    }

                    if (this["raids"][id]) {
                        /// TODO remove past raids
                        // end time is different -> new raid
                        if (this.raids[id]["end"] !== gym["raid"]["end"] || gym["raid"]["end"] > (new Date().getTime() / 1000)) {
                            map.removeLayer(leaflet_data.raids[id]);
                            delete leaflet_data.raids[id];
                        }
                    }

                    if (gym["raid"] && gym["raid"]["end"] > (new Date().getTime() / 1000)) {
                        if (map.hasLayer(leaflet_data.raids[id])) {
                            return;
                        }

                        this.raids[id] = gym["raid"];

                        const icon = L.divIcon({
                            html: gym["raid"]["level"],
                            className: "raidIcon",
                            iconAnchor: [-1 * (18 - map.getZoom()), -1 * (18 - map.getZoom())]
                        });

                        leaflet_data.raids[id] = L.marker([gym["lat"], gym["lon"]], {
                            id: id,
                            icon: icon,
                            interactive: false,
                            pane: layerOrders.raids.pane,
                            pmIgnore: true
                        });

                        this.mapAddLayer(leaflet_data.raids[id], layerOrders.raids.bringTo);
                    }
                }, this);
            });
        },
        map_fetch_routes() {
            this.mapGuardedFetch("routes", "get_route", function (res) {
                res.data.forEach(function (route) {
                    route.editableId = route.id

                    let hasUnappliedCounterpart = false;
                    if (Array.isArray(route.subroutes)) {
                        route.subroutes.forEach(function (subroute) {
                            subroute.mode = route.mode;
                            if (subroute.tag === "unapplied") {
                                hasUnappliedCounterpart = true;
                                subroute.editableId = route.id;
                            }
                        }, this);
                    }

                    const settingPrefix = "layers-dyn-routes-";
                    const routeSettingName = settingPrefix + route.id;
                    let show = this.getStoredSetting(routeSettingName, false);

                    // if the unapplied route was visible last time, but has been applied since, show the normal route instead
                    if (!hasUnappliedCounterpart) {
                        const unappliedRouteSettingName = routeSettingName + "_unapplied";
                        show = show || this.getStoredSetting(unappliedRouteSettingName, false);
                        this.updateStoredSetting(routeSettingName, show);
                        this.removeStoredSetting(unappliedRouteSettingName);
                    }

                    this.mapAddRoute(route, show);

                     if (Array.isArray(route.subroutes)) {
                         route.subroutes.forEach(function (subroute) {
                             this.mapAddRoute(subroute, this.getStoredSetting(settingPrefix + subroute.id, false));
                         }, this);
                     }
                }, this);
            });
        },
        map_fetch_prioroutes() {
            this.mapGuardedFetch("prioroutes", "get_prioroute", function (res) {
                res.data.forEach(function (route) {
                    const name = route.name;

                    if (this.layers.dyn.prioroutes[name]) {
                        map.removeLayer(leaflet_data.prioroutes[name]);
                    }

                    let mode;
                    let cradius;

                    if (route.mode === "mon_mitm" || route.mode === "iv_mitm") {
                        mode = "mons";
                        cradius = this.settings.routes.coordinateRadius.mons;
                    }
                    else if (route.mode === "pokestops") {
                        mode = "quests";
                        cradius = this.settings.routes.coordinateRadius.quests;
                    }
                    else if (route.mode === "raids_mitm") {
                        mode = "raids";
                        cradius = this.settings.routes.coordinateRadius.raids;
                    }

                    const linecoords = [];
                    const group = L.layerGroup();

                    // only display first 10 entries of the queue
                    const now = Math.round((new Date()).getTime() / 1000);
                    route.coordinates.slice(0, 14).forEach(function (coord, index) {
                        const until = coord.timestamp - now;
                        let hue;
                        let sat;

                        if (until < 0) {
                            hue = 0;
                            sat = 100;
                        }
                        else {
                            hue = 120;
                            sat = (index * 100) / 15;
                        }

                        const color = `hsl(${hue}, ${sat}%, 50%)`;

                        L.circle([coord.latitude, coord.longitude], {
                            ctimestamp: coord.timestamp,
                            radius: cradius,
                            color: color,
                            fillColor: color,
                            weight: 1,
                            opacity: 0.8,
                            fillOpacity: 0.5,
                            pmIgnore: true,
                            pane: layerOrders.routes.pane,
                        })
                        .bindPopup(this.build_prioq_popup)
                        .addTo(group);

                        linecoords.push([coord.latitude, coord.longitude]);
                    }, this);

                    // add route to layergroup
                    L.polyline(linecoords, {
                        "color": "#000000",
                        "weight": 2,
                        "opacity": 0.2,
                        "pane": layerOrders.routes.pane,
                        "pmIgnore": true
                    })
                    .bindPopup(this.build_prioq_route_popup(route), { className: "routepopup" })
                    .addTo(group);

                    // add layergroup to management object
                    leaflet_data.prioroutes[name] = group;

                    const settings = {
                        "show": this.getStoredSetting("layers-dyn-prioroutes-" + name, false),
                        "mode": mode
                    };

                    this.$set(this.layers.dyn.prioroutes, name, settings);

                }, this);
            });
        },
        map_fetch_spawns(urlFilter) {
            this.mapGuardedFetch("spawns", "get_spawns" + urlFilter, function (res) {
                res.data.forEach(function (spawns) {
                    const eventName = spawns["EVENT"];

                    spawns["Coords"].forEach(function (spawn) {
                        let color;

                        if (spawn["endtime"] !== null) {
                            const endsplit = spawn["endtime"].split(":");
                            const endMinute = parseInt(endsplit[0]);
                            const endSecond = parseInt(endsplit[1]);
                            const despawntime = moment();
                            const now = moment();

                            const timeshift = spawn["spawndef"] === 15 ? 60 : 30;

                            // setting despawn and spawn time
                            despawntime.minute(endMinute);
                            despawntime.second(endSecond);
                            const spawntime = moment(despawntime);
                            spawntime.subtract(timeshift, "m");

                            if (despawntime.isBefore(now)) {
                                // already despawned. shifting hours
                                spawntime.add(1, "h");
                                despawntime.add(1, "h");
                            }

                            if (now.isBetween(spawntime, despawntime)) {
                                color = "green";
                            }
                            else if (spawntime.isAfter(now)) {
                                color = "blue";
                            }
                        }
                        else {
                            color = "red";
                        }

                        const id = spawn["id"];
                        let skip = true;

                        if (this.spawns[eventName] && this.spawns[eventName][id]) {
                            // check if we should update an existing spawn
                            if (this.spawns[eventName][id]["endtime"] === null && spawn["endtime"] !== null) {
                                map.removeLayer(leaflet_data.spawns[eventName][id]);
                                delete leaflet_data.spawns[eventName][id];
                            }
                            else {
                                skip = false;
                            }
                        }

                        if (skip) {
                            // store spawn meta data
                            if (!this.spawns[eventName]) {
                                this.spawns[eventName] = {};
                            }

                            this.spawns[eventName][id] = spawn;

                            if (!leaflet_data.spawns[eventName]) {
                                leaflet_data.spawns[eventName] = {};
                            }

                            leaflet_data.spawns[eventName][id] = L.circle([spawn["lat"], spawn["lon"]], {
                                radius: 2,
                                color: color,
                                fillColor: color,
                                weight: 1,
                                opacity: 0.7,
                                fillOpacity: 0.5,
                                id: id,
                                event: eventName,
                                pane: layerOrders.spawns.pane,
                                pmIgnore: true
                            }).bindPopup(this.build_spawn_popup, { "className": "spawnpopup" });

                            this.addMouseEventPopup(leaflet_data.spawns[eventName][id]);
                        }
                    }, this);

                    const settings = {
                        "show": this.getStoredSetting("layers-dyn-spawns-" + eventName, false)
                    };
                    this.$set(this.layers.dyn.spawns, eventName, settings);

                }, this);
            });
        },
        map_fetch_quests(urlFilter) {
            if (!this.layers.stat.quests) {
                return;
            }

            this.mapGuardedFetch("quests", "get_quests" + urlFilter, function (res) {
                res.data.forEach(function (quest) {
                    const id = quest["pokestop_id"];

                    if (this.quests[id]) {
                        return;
                    }

                    this.quests[id] = quest;

                    leaflet_data.quests[id] = L.marker([quest["latitude"], quest["longitude"]], {
                        id: id,
                        virtual: true,
                        icon: this.build_quest_small(
                            quest["quest_reward_type_raw"],
                            quest["item_id"],
                            quest["pokemon_id"],
                            quest["pokemon_form"],
                            quest["pokemon_asset_bundle_id"],
                            quest["pokemon_costume"]),
                        pane: layerOrders.quests.pane,
                        pmIgnore: true
                    }).bindPopup(this.build_quest_popup, { "className": "questpopup" });

                    this.addMouseEventPopup(leaflet_data.quests[id]);

                    if (this.layers.stat.quests) {
                        this.mapAddLayer(leaflet_data.quests[id], layerOrders.quests.bringTo);
                    }

                }, this);
            });
        },
        map_fetch_stops(urlFilter) {
            if (!this.layers.stat.stops) {
                return;
            }

            this.mapGuardedFetch("stops", "get_stops" + urlFilter, function(res) {
                res.data.forEach(function(stop) {
                    const id = stop["pokestop_id"];

                    if (this.stops[id]) {
                        return;
                    }

                    const color = stop["has_quest"] ? "blue" : "red";
                    this.stops[id] = stop;
                    leaflet_data.stops[id] = L.circle([stop["latitude"], stop["longitude"]], {
                        radius: 8,
                        color: color,
                        fillColor: color,
                        weight: 1,
                        opacity: 0.7,
                        fillOpacity: 0.5,
                        pane: layerOrders.stops.pane,
                        pmIgnore: true,
                        id: id
                    }).bindPopup(this.build_stop_popup, { "className": "stoppopup" });
                    this.addMouseEventPopup(leaflet_data.stops[id]);

                    if (this.layers.stat.stops) {
                        this.mapAddLayer(leaflet_data.stops[id], layerOrders.stops.bringTo);
                    }

                }, this);
            });
        },
        map_fetch_geofences() {
            this.mapGuardedFetch("geofences", "get_geofences", function (res) {
                res.data.forEach(function(geofence) {
                    this.mapAddGeofence(geofence, this.getStoredSetting("layers-dyn-geofences-" + geofence.id, false));
                }, this);
            });
        },
        map_fetch_areas() {
            this.mapGuardedFetch("areas", "get_areas", function (res) {
                res.data.forEach(function(area) {
                    const name = area.name;

                    if (this.layers.dyn.areas[name]) {
                        return;
                    }

                    const polygon = L.polygon(area.coordinates, {
                        color: this.getRandomBackgroundColor(),
                        weight: 2,
                        opacity: 0.5,
                        pane: layerOrders.areas.pane,
                        pmIgnore: true
                    }).bindPopup(this.build_area_popup(area), { className: "areapopup" });

                    leaflet_data.areas[name] = polygon;

                    const settings = {
                        show: this.getStoredSetting("layers-dyn-areas-" + name, false)
                    };
                    this.$set(this.layers.dyn.areas, name, settings);

                }, this);
            });
        },
        map_fetch_mons(urlFilter) {
            if (!this.layers.stat.mons) {
                return;
            }

            this.mapGuardedFetch("mons", "get_map_mons" + urlFilter, function (res) {
                res.data.forEach(function (mon) {
                    const id = mon["encounter_id"];

                    if (this.mons[id]) {
                        if (this.mons[id]["last_modified"] === mon["last_modified"]) {
                            return;
                        }

                        map.removeLayer(leaflet_data.mons[id]);
                        delete leaflet_data.mons[id];
                    }

                    // store meta data
                    this.mons[id] = mon;

                    const monId = mon["mon_id"];
                    let icon;
                    if (leaflet_data.monicons[monId]) {
                        icon = leaflet_data.monicons[monId];
                    }
                    else {
                        const form = mon["form"] === 0 ? "00" : mon["form"];
                        const image = `${iconBasePath}/pokemon_icon_${monId.toString().padStart(3, "0")}_${form}.png`;
                        icon = L.icon({
                            iconUrl: image,
                            iconSize: [40, 40]
                        });

                        leaflet_data.monicons[monId] = icon;
                    }

                    leaflet_data.mons[id] = L.marker([mon["latitude"], mon["longitude"]], {
                        id: id,
                        virtual: true,
                        icon: icon,
                        pane: layerOrders.mons.pane,
                        pmIgnore: true
                    }).bindPopup(this.build_mon_popup, {"className": "monpopup"});

                    this.addMouseEventPopup(leaflet_data.mons[id]);

                    // only add them if they're set to visible
                    if (this.layers.stat.mons) {
                        this.mapAddLayer(leaflet_data.mons[id], layerOrders.mons.bringTo);
                    }

                }, this);
            });
        },
        map_fetch_cells(urlFilter) {
            if (!this.layers.stat.cellupdates) {
                return;
            }

            var $this = this;

            this.mapGuardedFetch("cellupdates", "get_cells" + urlFilter, function (res) {
                const now = Math.round((new Date()).getTime() / 1000);

                res.data.forEach(function (cell) {
                    const id = cell["id"];

					var noSkip = true;
                    var notTooOld = true;
                    if (this.cellupdates[id]) {
                        if (this.cellupdates[id]["updated"] === cell["updated"]) {
                            noSkip = false;
                        } else {
                        	map.removeLayer(leaflet_data.cellupdates[id]);
                        	delete leaflet_data.cellupdates[id];
                        }
                    }
                    //  86400
                    if($this.settings.cellUpdateTimeout > 0 && now - cell.updated > $this.settings.cellUpdateTimeout) {
                        notTooOld = false;
                    }

                    if (noSkip && notTooOld) {
                        $this.cellupdates[id] = cell;

                    	leaflet_data.cellupdates[id] = L.polygon(cell["polygon"], {
                            id: id,
                            pane: layerOrders.cells.pane,
                            pmIgnore: true
                        })
                        .setStyle(this.getCellStyle(now, cell["updated"]))
                        .bindPopup(this.build_cell_popup, { className: "cellpopup" });

                    	this.mapAddLayer(leaflet_data.cellupdates[id], layerOrders.cells.bringTo);
                    }

                }, this);
            });
        },
        mapGuardedFetch(guardName, url, onSuccess) {
            if (this.fetchers[guardName]) {
                return;
            }

            this.fetchers[guardName] = true;

            axios.get(url)
                .then(onSuccess.bind(this))
                .finally(function () { this.fetchers[guardName] = false; }.bind(this));
        },
        mapAddGeofence(geofence, show) {
            const id = geofence.id;

            if (this.layers.dyn.geofences[id]) {
                return;
            }

            const polygon = L.polygon(geofence.coordinates, {
                color: this.getRandomBackgroundColor(),
                weight: 2,
                opacity: 0.5,
                pane: layerOrders.geofences.pane
            });

            polygon.bindPopup(
                this.build_geofence_popup(geofence.id, geofence.name, polygon, function (name) { geofence.name = name; }),
                { className: "geofencepopup" });

            leaflet_data.geofences[id] = polygon;

            this.$set(this.layers.dyn.geofences, id, {
                id: geofence.id,
                name: geofence.name,
                show: show
            });
        },
        mapAddRoute(route, show) {
            const id = route.id;

            if (this.layers.dyn.routes[id]) {
                return;
            }

            let modeDisplay;
            let cradius;

            if (route.mode === "mon_mitm") {
                modeDisplay = "mons";
                cradius = this.settings.routes.coordinateRadius.mons;
            }
            else if (route.mode === "pokestops") {
                modeDisplay = "quests";
                cradius = this.settings.routes.coordinateRadius.quests;
            }
            else if (route.mode === "raids_mitm") {
                modeDisplay = "raids";
                cradius = this.settings.routes.coordinateRadius.raids;
            }
            else {
                modeDisplay = route.mode;
                cradius = 0;
            }

            let stack = [];
            let processedCells = {};

            const group = L.layerGroup();
            const color = this.getRandomForegroundColor();
            const circleOptions = {
                radius: cradius,
                color: color,
                fillColor: color,
                weight: 1,
                opacity: 0.4,
                fillOpacity: 0.2,
                interactive: false,
                pane: layerOrders.routes.pane,
                pmIgnore: true
            };

            const circles = [];

            route.coordinates.forEach(function (coord) {
                const circle = L.circle(coord, circleOptions);
                circles.push(circle);
                circle.addTo(group);

                if (route.mode === "raids_mitm") {
                    // super dirty workaround to get bounds
                    // of a circle. The getbounds() function
                    // is only available if it has been added
                    // to the map.
                    // See https://github.com/Leaflet/Leaflet/issues/4978
                    circle.addTo(map);
                    const bounds = circle.getBounds();
                    circle.removeFrom(map);

                    const centerCell = S2.S2Cell.FromLatLng(circle.getLatLng(), 15)
                    processedCells[centerCell.toString()] = true
                    stack.push(centerCell)
                    L.polygon(centerCell.getCornerLatLngs(), {
                        color: color,
                        opacity: 0.5,
                        weight: 1,
                        fillOpacity: 0,
                        interactive: false,
                        pane: layerOrders.cells.pane,
                        pmIgnore: true
                    }).addTo(group);

                    while (stack.length > 0) {
                        const cell = stack.pop();
                        const neighbors = cell.getNeighbors()
                        neighbors.forEach(function (ncell) {
                            if (processedCells[ncell.toString()] !== true) {
                                const cornerLatLngs = ncell.getCornerLatLngs();

                                for (let i = 0; i < 4; i++) {
                                    const item = cornerLatLngs[i];
                                    const distance = L.latLng(item.lat, item.lng).distanceTo(circle.getLatLng());
                                    if (item.lat >= bounds.getSouthWest().lat
                                        && item.lng >= bounds.getSouthWest().lng
                                        && item.lat <= bounds.getNorthEast().lat
                                        && item.lng <= bounds.getNorthEast().lng
                                        && distance <= cradius) {
                                        processedCells[ncell.toString()] = true;
                                        stack.push(ncell);
                                        L.polygon(ncell.getCornerLatLngs(), {
                                            color: color,
                                            opacity: 0.5,
                                            weight: 1,
                                            fillOpacity: 0,
                                            interactive: false,
                                            pane: layerOrders.cells.pane,
                                            pmIgnore: true,
                                        }).addTo(group);
                                        break
                                    }
                                }
                            }
                        })
                    }
                }
            });

            const polyline = L.polyline(route.coordinates, {
                color: color,
                weight: 3,
                opacity: 1.0,
                pane: layerOrders.routes.pane
            });

            polyline
                .bindPopup(this.build_route_popup(route, polyline, circles, group, circleOptions), { className: "routepopup" })
                .addTo(group);

            leaflet_data.routes[id] = group;

            this.$set(this.layers.dyn.routes, id, {
                id: id,
                name: route.name,
                tag: route.tag,
                mode: modeDisplay,
                show: show
            });
        },
        mapAddLayer(layer, bringTo) {
            map.addLayer(layer);

            if (typeof bringTo === "string" && typeof layer[bringTo] === "function") {
                layer[bringTo]();
            }

            if (layer instanceof L.LayerGroup) {
                layer.eachLayer(this.configureVisibleLayerMouseEvents);
            }
            else {
                this.configureVisibleLayerMouseEvents(layer);
            }
        },
        configureVisibleLayerMouseEvents(layer) {
            if (!(layer instanceof L.Path) || !layer.options.interactive) {
                return;
            }

            const originalOpacity = layer.options.opacity;
            const originalWeight = layer.options.weight;

            layer.on("mouseover", onMouseOver);
            layer.on("mouseout", onMouseOut);
            layer.on("remove", onRemove);

            function onMouseOver() {
                if (!mouseEventsIgnore.isIgnored()) {
                    layer.setStyle({ opacity: 1.0, weight: originalWeight + 2.0 })
                }
            }

            function onMouseOut() {
                if (!mouseEventsIgnore.isIgnored() && !(layer.pm && layer.pm.enabled())) {
                    layer.setStyle({ opacity: originalOpacity, weight: originalWeight });
                }
            }

            function onRemove() {
                layer.off("mouseover", onMouseOver);
                layer.off("mouseout", onMouseOut);
                layer.off("remove", onRemove);
            }
        },
        changeDynamicLayers(type, hasMultipleLayersPerType, bringTo) {
            for (const key in this.layers.dyn[type]) {
                const show = this.layers.dyn[type][key].show;
                this.updateStoredSetting(`layers-dyn-${type}-${key}`, show);

                function showHideLayer(layer) {
                    if (!show) {
                        map.removeLayer(layer);
                    }
                    else if (!map.hasLayer(layer)) {
                        this.mapAddLayer(layer, bringTo);
                    }
                }

                if (hasMultipleLayersPerType) {
                    const layers = leaflet_data[type][key];
                    for (const prop in layers) {
                        if (typeof layers[prop] === "object") {
                            showHideLayer.call(this, layers[prop]);
                        }
                    }
                }
                else {
                    showHideLayer.call(this, leaflet_data[type][key]);
                }
            }
        },
        changeStaticLayer(name, oldState, newState, bringTo) {
            const layers = leaflet_data[name];
            if (oldState === true) {
                Object.keys(layers).forEach(function (key) {
                    map.removeLayer(layers[key]);
                }, this);
            }
            else {
                Object.keys(layers).forEach(function (key) {
                    this.mapAddLayer(layers[key], bringTo);
                }, this);
            }

            this.updateStoredSetting("layer-stat-" + name, newState);
        },
        getCellStyle(now, cell_updated) {
            // credits to RDM for this

            let ago = now - cell_updated;
            let value;

            if (ago <= 150) {
                value = 0;
            } else {
                value = Math.min((ago - 150) / 750, 1);
            }

            const hue = ((1 - value) * 120).toString(10);
            return {
                fillColor: `hsl(${hue}, 100%, 50%)`,
                color: "#333",
                opacity: 0.65,
                fillOpacity: 0.4,
                weight: 1
            };
        },
        getRandomForegroundColor() {
            return this.getHslColor(Math.floor(Math.random() * 360), 80, 30);
        },
        getRandomBackgroundColor() {
            return this.getHslColor(Math.floor(Math.random() * 360), 30, 50);
        },
        getHslColor(hue, saturation, lightness) {
            return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        },
        build_cell_popup(marker) {
            var cell = this.cellupdates[marker.options.id];

            return `
        <div class="content">
          <div class="id"><i class="fa fa-fingerprint"></i> <span>${cell["id"]}</span></div>
          <div id="updated"><i class="fa fa-clock"></i> Updated: ${moment(cell['updated'] * 1000).format("YYYY-MM-DD HH:mm:ss")}</div>
        </div>`;
        },
        build_prioq_popup(marker) {
            const time = moment(marker.options.ctimestamp * 1000);
            return `Due: ${time.format("YYYY-MM-DD HH:mm:ss")} (${marker.options.ctimestamp})`;
        },
        build_prioq_route_popup(route) {

            const popupContainer = $(`
              <div>
                <div class="name"><i class="fas fa-sort-numeric-up"></i> <strong></strong></div>
                <div><i class="fas fa-adjust"></i> Mode: <span class="badge badge-secondary"></span></div>
                <div><i class="fas fa-ruler-horizontal"></i> Length: <strong class="length"></strong></div>
              </div>
            `);

            $(".name strong", popupContainer).text(route.name);
            $(".badge", popupContainer).text(route.mode);
            $(".length", popupContainer).text(route.coordinates.length);

            return popupContainer[0];
        },
        build_quest_small(quest_reward_type_raw, quest_item_id, quest_pokemon_id, quest_pokemon_form_id, quest_pokemon_asset_bundle_id, quest_pokemon_costume_id) {
            switch (quest_reward_type_raw) {
                case 2:
                    var image = `${iconBasePath}/rewards/reward_${quest_item_id}_1.png`;
                    var size = [30, 30]
                    var anchor = [30, 30]
                    break;
                case 3:
                    var image = `${iconBasePath}/rewards/reward_stardust.png`;
                    var size = [30, 30]
                    var anchor = [30, 30]
                    break;
                case 7:
                    var costume = '';
                    var asset_bundle = quest_pokemon_asset_bundle_id || '00';
                    if (quest_pokemon_costume_id != '00') {
                        costume = '_' + quest_pokemon_costume_id;
                    }
                    var image = `${iconBasePath}/pokemon_icon_${String.prototype.padStart.call(quest_pokemon_id, 3, 0)}_${quest_pokemon_form_id}${costume}.png`;
                    var size = [30, 30]
                    var anchor = [30, 30]
                    break;
                case 12:
                    var image = 'https://raw.githubusercontent.com/whitewillem/PogoAssets/resized/icons_large/rewards/reward_mega_energy.png'
                    var size = [30, 30]
                    var anchor = [30, 30]
                    break;
            }

            var icon = L.icon({
                iconUrl: 'static/Pstop-quest.png',
                shadowUrl: image,
                iconSize: [30, 30],
                iconAnchor: [15, 30],
                shadowSize: size,
                shadowAnchor: anchor
            })

            return icon;
        },
        build_quest(quest_reward_type_raw, quest_task, quest_pokemon_id, quest_pokemon_form_id, quest_pokemon_asset_bundle_id, quest_pokemon_costume_id, quest_item_id, quest_item_amount, quest_pokemon_name, quest_item_type) {
            var size = "100%";

            switch (quest_reward_type_raw) {
                case 2:
                    var image = `${iconBasePath}/rewards/reward_${quest_item_id}_1.png`;
                    var rewardtext = `${quest_item_amount}x ${quest_item_type}`;
                    break;
                case 3:
                    var image = `${iconBasePath}/rewards/reward_stardust.png`;
                    var rewardtext = `${quest_item_amount} ${quest_item_type}`;
                    break;
                case 7:
                    var costume = '';
                    var asset_bundle = quest_pokemon_asset_bundle_id || '00';
                    if (quest_pokemon_costume_id != '00') {
                        costume = '_' + quest_pokemon_costume_id;
                    }
                    var image = `${iconBasePath}/pokemon_icon_${String.prototype.padStart.call(quest_pokemon_id, 3, 0)}_${quest_pokemon_form_id}${costume}.png`;
                    var rewardtext = quest_pokemon_name;
                    var size = "150%";
                    break;
                case 12:
                    var image = 'https://raw.githubusercontent.com/whitewillem/PogoAssets/resized/icons_large/rewards/reward_mega_energy.png'
                    var rewardtext =  `${quest_item_amount} ${quest_item_type} ${quest_pokemon_name}`;
                    break;
            }

            return `
        <div class="quest">
          <div class="task"><i class="fa fa-question-circle"></i> Task: <strong>${quest_task}</strong></div>
          <div class="reward"><i class="fa fa-trophy"></i> Reward: <strong>${rewardtext}</strong></div>
          <div class="rewardImg" style="background-image: url(${image}); background-size: ${size}"></div>
        </div>`;
        },
        build_stop_base_popup(id, image, name, latitude, longitude) {
            return `
          <div class="image" style="background: url(${image}) center center/cover no-repeat;"></div>
          <div class="name"><strong>${name}</strong></div>
          <div class="id"><i class="fa fa-fingerprint"></i> <span>${id}</span></div>
          <div class="coords">
            <i class="fa fa-map-pin"></i>
            <a href="https://maps.google.com/?q=${latitude},${longitude}">${latitude}, ${longitude}</a>
            <a onclick=copyClipboard("${latitude.toFixed(6)}|${longitude.toFixed(6)}") href="#"><i class="fa fa-clipboard" aria-hidden="true"></i></a>
          </div>`
        },
        build_quest_popup(marker) {
            var quest = this.quests[marker.options.id]
            quest["url"] = quest["url"].replace('http://', 'https://');
            var base_popup = this.build_stop_base_popup(quest["pokestop_id"], quest["url"], quest["name"], quest["latitude"], quest["longitude"])

            return `
        <div class="content">
          ${base_popup}
          <div id="questTimestamp"><i class="fa fa-clock"></i> Scanned: <strong>${moment(quest['timestamp'] * 1000).local().format("YYYY-MM-DD HH:mm:ss")}</strong></div>
          <br>
          ${this.build_quest(quest['quest_reward_type_raw'], quest['quest_task'], quest['pokemon_id'], quest['pokemon_form'], quest['pokemon_asset_bundle_id'], quest['pokemon_costume'], quest['item_id'], quest['item_amount'], quest['pokemon_name'], quest['item_type'])}
        </div>`;
        },
        build_stop_popup(marker) {
            var stop = this.stops[marker.options.id];
            var base_popup = this.build_stop_base_popup(stop["pokestop_id"], stop["image"], stop["name"], stop["latitude"], stop["longitude"])

            var incident = "";
            var incident_expiration = moment.utc(stop["incident_expiration"] * 1000);
            if (incident_expiration.isAfter(moment.utc())) {
                incident = `<div class="incident"><i class="fa fa-user-secret"></i> Incident ends: <strong>${incident_expiration.local().format("YYYY-MM-DD HH:mm:ss")}</strong></div>`
            }

            var lure = "";
            var lure_expiration = moment.utc(stop["lure_expiration"] * 1000);
            if (lure_expiration.isAfter(moment())) {
                lure = `<div class="incident"><i class="fa fa-drumstick-bite"></i> Lure ends: <strong>${lure_expiration.local().format("YYYY-MM-DD HH:mm:ss")}</strong></div>`
            }
            return `
        <div class="content">
          ${base_popup}
          <br>
          <div class="timestamp"><i class="fa fa-clock"></i> Scanned: <strong>${moment.utc(stop["last_updated"] * 1000).local().format("YYYY-MM-DD HH:mm:ss")}</strong></div>
          ${incident}
          ${lure}
        </div>`;
        },
        build_gym_popup(marker) {
            gym = this.gyms[marker.options.id];
            raid = this.raids[marker.options.id];

            raidContent = "";
            if (raid) {
                var monText = "";
                if (raid["mon"]) {
                    var mon = String.prototype.padStart.call(raid["mon"], 3, 0);
                    var form = String.prototype.padStart.call(raid["form"], 2, 0);
                    var image = `${iconBasePath}/pokemon_icon_${mon}_${form}.png`;
                    var monText = `<div class="monId"><i class="fas fa-ghost"></i> Mon: <strong>#${raid["mon"]}</strong></div>`
                } else {
                    var image = `${iconBasePath}/egg${raid["level"]}.png`;
                }

                var levelStars = `<i class="fas fa-star"></i>`.repeat(raid["level"]);

                var now = moment();
                var spawn = moment(raid["spawn"] * 1000);
                var start = moment(raid["start"] * 1000);
                var end = moment(raid["end"] * 1000);

                var activeText = "";
                var endText = "";
                if (now.isAfter(start) && now.isBefore(end)) {
                    var activeText = `<span class="text-success">(active <i class="fa fa-ghost"></i>)</span>`;
                    var endText = `(${now.to(end)})`;
                } else if (now.isBefore(start)) {
                    var activeText = `(${now.to(start)})`;
                } else if (now.isAfter(end)) {
                    var endText = `(${end.from(now)})`;
                }

                var raidtimeformat = "HH:mm:ss";
                var raidContent = `
          <br>
          <div class="raid">
            <div class="level"><i class="fas fa-arrow-circle-up"></i> Level: <strong>${levelStars}</strong></div>
            ${monText}
            <div class="hatch"><i class="fa fa-egg"></i> Spawn: <strong>${spawn.format(raidtimeformat)}</strong></div>
            <div class="start"><i class="fa fa-hourglass-start"></i> Start: <strong>${start.format(raidtimeformat)} ${activeText}</strong></div>
            <div class="end"><i class="fas fa-hourglass-end"></i> End: <strong>${end.format(raidtimeformat)} ${endText}</strong></div>
            <div class="monImg" style="background-image: url(${image}); background-size: 100%"></div>
          </div>`;
            }

            var gymName = gym["name"] != "unknown" ? gym["name"] : teamNames[gym["team_id"]] + " Gym"
            var timeformat = "YYYY-MM-DD HH:mm:ss";
            var last_scanned = moment(gym["last_scanned"] * 1000);

            return `
        <div class="content">
          <div class="image" style="background: url(${gym["img"]}) center center/cover no-repeat;"></div>
          <div class="name"><strong>${gymName}</strong></div>
          <div class="id"><i class="fa fa-fingerprint"></i> <span>${gym["id"]}</span></div>
          <div class="coords">
            <i class="fa fa-map-pin"></i>
            <a href="https://maps.google.com/?q=${gym["lat"]},${gym["lon"]}">${gym["lat"]}, ${gym["lon"]}</a>
            <a onclick=copyClipboard("${gym["lat"].toFixed(6)}|${gym["lon"].toFixed(6)}") href="#"><i class="fa fa-clipboard" aria-hidden="true"></i></a>
         </div>
         <div class="timestamp"><i class="fa fa-clock"></i> Scanned: ${last_scanned.format(timeformat)}</div>
         ${raidContent}
         <br>
         <button id="sendworker" class="btn btn-outline-secondary btn-sm" data-loc="${gym["lat"]},${gym["lon"]}"><i class="fas fa-satellite-dish"></i> Send worker here</button>
        </div>`;
        },
        build_spawn_popup(marker) {
            spawn = this.spawns[marker.options.event][marker.options.id];

            if (spawn['endtime'] !== null) {
                var timeformat = "YYYY-MM-DD HH:mm:ss";

                var endsplit = spawn['endtime'].split(':');
                var endMinute = parseInt(endsplit[0]);
                var endSecond = parseInt(endsplit[1]);
                var despawntime = moment();
                var now = moment();

                if (spawn['spawndef'] == 15) {
                    var type = '1h';
                    var timeshift = 60;
                } else {
                    var type = '30m';
                    var timeshift = 30;
                }

                // setting despawn and spawn time
                despawntime.minute(endMinute);
                despawntime.second(endSecond);
                var spawntime = moment(despawntime);
                spawntime.subtract(timeshift, 'm');

                if (despawntime.isBefore(now)) {
                    // already despawned. shifting hours
                    spawntime.add(1, 'h');
                    despawntime.add(1, 'h');
                }

                var activeText = "";
                if (now.isBetween(spawntime, despawntime)) {
                    var activeText = `<span class="text-success">(active <i class="fa fa-ghost"></i>)</span>`;
                }

                var spawntiming = `
          <div class="spawn"><i class="fa fa-hourglass-start"></i> Spawn: <strong>${spawntime.format(timeformat)} ${activeText}</strong></div>
          <div class="despawn"><i class="fa fa-hourglass-end"></i> Despawn: <strong>${despawntime.format(timeformat)}</strong></div>`
            } else {
                var spawntiming = ""
            }

            const lastMon = spawn["lastscan"] > spawn["lastnonscan"] ? spawn["lastscan"] : spawn["lastnonscan"]

            return `
        <div class="content">
          <div  class="id"><i class="fa fa-fingerprint"></i> <span>${spawn["id"]}</span></div>
          <div class="coords">
            <i class ="fa fa-map-pin"></i>
            <a href="https://maps.google.com/?q=${spawn["lat"]},${spawn["lon"]}">${spawn["lat"].toFixed(6)}, ${spawn["lon"].toFixed(6)}</a>
         </div>
         <br>
          <div cla ss="spawnContent">
            <div class="spawnFirstDetection"><i class="fas fa-baby"></i> First seen: <strong>${moment(spawn["first_detection"] * 1000).format("YYYY-MM-DD HH:mm:ss")}</strong></div>
            <div class="timestamp"><i class="fas fa-eye"></i> <abbr title="This is the time a mon has been seen on this spawnpoint.">Last mon seen</abbr>: <strong>${lastMon}</strong></div>
            <div class="timestamp"><i class="fa fa-clock"></i> <abbr title="The timestamp of the last time this spawnpoint's despawn time has been confirmed.">Last confirmation</abbr>: <strong>${spawn["lastscan"]}</strong></div>
            <div class="spawnType"><i class="fa fa-wrench"></i> Type: <strong>${type || "Unknown despawn time"}</strong></div>
            <div class="spawnType"><i class="fas fa-calendar-week"></i></i> Event- / Spawntype: <strong>${spawn["event"]}</strong></div>
            <div class="spawnTiming">${spawntiming}</div>
          </div>
        </div>`;
        },
        build_mon_popup(marker) {
            mon = this.mons[marker.options.id];

            var form = mon["form"] == 0 ? "00" : mon["form"];
            var image = `${iconBasePath}/pokemon_icon_${String.prototype.padStart.call(mon["mon_id"], 3, 0)}_${form}.png`;

            var iv = (mon["individual_attack"] + mon["individual_defense"] + mon["individual_stamina"]) * 100 / 45;
            var end = moment(mon["disappear_time"] * 1000);

            if (iv == 100) {
                var ivcolor = "lime";
            } else if (iv >= 82) {
                var ivcolor = "green";
            } else if (iv >= 66) {
                var ivcolor = "olive";
            } else if (iv >= 51) {
                var ivcolor = "orange";
            } else {
                var ivcolor = "red";
            }

            var ivtext = "";
            if (mon["cp"] > 0) {
                ivtext = `
            <div class="iv">
              <i class="fas fa-award"></i> IV: <strong style="color: ${ivcolor}">${Math.round(iv * 100) / 100}%</strong>
              (Att: <strong>${mon["individual_attack"]}</strong> | Def: <strong>${mon["individual_defense"]}</strong> | Sta: <strong>${mon["individual_stamina"]}</strong>)
            </div>
            <div class="measurements">
              <i class="fas fa-ruler-vertical"></i> Height: <strong>${mon["height"].toFixed(2)}</strong>
              <i class="fas fa-weight-hanging"></i> Weight: <strong>${mon["weight"].toFixed(2)}</strong>
            </div>`;
            }

            return `
        <div class="content">
          <div class="name"><strong>${mon["name"]}</strong> #${mon["mon_id"]} ${mon["gender"] == 1 ? '<i class="fas fa-mars"></i>' : '<i class="fas fa-venus"></i>'}</div>
          <div class="id"><i class="fa fa-fingerprint"></i> <span>${mon["encounter_id"]}</span></div>
          <div class="coords">
            <i class="fa fa-map-pin"></i>
            <a href="https://maps.google.com/?q=${mon["latitude"]},${mon["longitude"]}">${mon["latitude"].toFixed(6)}, ${mon["longitude"].toFixed(6)}</a>
            <a onclick=copyClipboard("${mon["latitude"].toFixed(6)}|${mon["longitude"].toFixed(6)}") href="#"><i class="fa fa-clipboard" aria-hidden="true"></i></a>
         </div>
          <div id="timestamp"><i class="fa fa-clock"></i> Modified: ${moment(mon['last_modified'] * 1000).format("YYYY-MM-DD HH:mm:ss")}</div>
          <br>
          ${ivtext}
        <div class="end"><i class="fas fa-hourglass-end"></i> Despawn: <strong>${end.format("YYYY-MM-DD HH:mm:ss")} (${end.from(moment())})</strong></div>
        <br>
        <button id="sendworker" class="btn btn-outline-secondary btn-sm" data-loc="${mon["latitude"].toFixed(6)},${mon["longitude"].toFixed(6)}"><i class="fas fa-satellite-dish"></i> Send worker here</button>
        <div class="monImg" style="background-image: url(${image}); background-size: 100%"></div>
        </div>
      `;
        },
        build_route_popup(route, polyline, circles, layerGroup, circleOptions) {
            const mainContent = $(`
              <div>
                <div class="name"><i class="fa fa-route"></i> <strong></strong></div>
                <div><i class="fas fa-adjust"></i> Mode: <span class="badge badge-secondary"></span></div>
                <div><i class="fas fa-ruler-horizontal"></i> Length: <strong class="length"></strong></div>
              </div>
            `);

            $(".name strong", mainContent).text(route.name);
            $(".badge", mainContent).text(route.mode);
            $(".length", mainContent).text(route.coordinates.length);

            if (route.mode === "mon_mitm" && typeof route.editableId === "number") {

                function getCircleIndex(event) {
                    return event.indexPath[0];
                }

                function onMarkerDrag(event) {
                    const circle = event.target.associatedCircle;
                    if (circle) {
                        circle.setLatLng(event.latlng);
                    }
                }

                function onMarkerDragStart(event) {
                    const marker = event.markerEvent.target;
                    marker.associatedCircle = circles[getCircleIndex(event)];
                    marker.on("drag", onMarkerDrag);
                }

                function onMarkerDragEnd(event) {
                    const marker = event.markerEvent.target;
                    delete marker.associatedCircle;
                    marker.off("drag", onMarkerDrag);
                }

                function onVertexAdded(event) {
                    const circle = L.circle(event.latlng, circleOptions);
                    circles.splice(getCircleIndex(event), 0, circle);
                    circle.addTo(layerGroup);
                }

                function onVertexRemoved(event) {
                    const index = getCircleIndex(event);
                    const circle = circles[index]
                    circle.remove()
                    circles.splice(index, 1)
                }

                polyline.on("pm:enable", function () {
                    polyline.on("pm:markerdragstart", onMarkerDragStart);
                    polyline.on("pm:markerdragend", onMarkerDragEnd);
                    polyline.on("pm:vertexadded", onVertexAdded);
                    polyline.on("pm:vertexremoved", onVertexRemoved);
                })

                polyline.on("pm:disable", function () {
                    polyline.off("pm:markerdragstart", onMarkerDragStart);
                    polyline.off("pm:markerdragend", onMarkerDragEnd);
                    polyline.off("pm:vertexadded", onVertexAdded);
                    polyline.off("pm:vertexremoved", onVertexRemoved);
                })

                function restoreOriginalCircles(originalLatLngs) {
                    circles.forEach(function (circle) { circle.remove() })
                    circles.splice(0, circles.length)

                    if (Array.isArray(originalLatLngs)) {
                        originalLatLngs.forEach(function (latLng) {
                            const circle = L.circle(latLng, circleOptions);
                            circles.push(circle);
                            circle.addTo(layerGroup);
                        })
                    }
                }

                return this.build_editable_popup(
                    mainContent, route.editableId, polyline, "route", true,
                    function (coords) {
                        return axios.patch("api/routecalc/" + route.editableId, { routefile: coords })
                    },
                    function (result, originalLatLngs) {
                        // we've just edited an applied route:
                        //  - clone that edited routed has an unapplied route
                        //  - restore the route before modifications as the applied one
                        if (route.id === route.editableId) {
                            const unappliedRouteId = route.id + "_unapplied";
                            if (this.layers.dyn.routes[unappliedRouteId]) {
                                this.$delete(this.layers.dyn.routes, unappliedRouteId);
                                leaflet_data.routes[unappliedRouteId].removeFrom(map);
                            }

                            const unappliedRoute = Object.assign({ }, route);
                            unappliedRoute.id = unappliedRouteId;
                            unappliedRoute.name = route.name + " (unapplied)";
                            unappliedRoute.tag = "unapplied";
                            unappliedRoute.coordinates = polyline.getLatLngs().map(function (latLng) { return [latLng.lat, latLng.lng] });
                            this.mapAddRoute(unappliedRoute, true);

                            polyline.setLatLngs(originalLatLngs);
                            restoreOriginalCircles(originalLatLngs);
                            this.layers.dyn.routes[route.id].show = false;
                        }
                    },
                    restoreOriginalCircles
                )
            }

            return mainContent[0];
        },
        build_geofence_popup(id, name, layer, onNameChanged) {
            const mainContent = $(`
              <div>
                <div class="name">
                  <i class="fa fa-draw-polygon"></i>
                  <strong>
                    <span class="map-popup-group-edit"></span>
                    <input type="text" class="map-popup-group-save hidden" />
                  </strong>
                </div>
              </div>`
            );

            const nameSpan = $(".name span", mainContent);
            const nameInput = $(".name input", mainContent);
            nameSpan.text(name);
            nameInput.val(name);

            return this.build_editable_popup(
                mainContent, id, layer, "geofence", false,
                function (coords) {
                    const json = {
                        name: nameInput.val(),
                        fence_type: "polygon",
                        fence_data: coords
                    }

                    return id === null
                        ? axios.post("api/geofence", json)
                        : axios.patch("api/geofence/" + id, json);
                },
                function (result) {
                    if (id === null) {
                        // we've added a new geofence, remove the temporary polygon (which is on a top-most pane)
                        // and add a standard geofence on the correct pane instead
                        map.removeLayer(layer);

                        const match = /\/(\d+)$/.exec(result.headers["x-uri"]);
                        if (match !== null) {
                            this.mapAddGeofence({
                                id: match[1],
                                name: nameInput.val(),
                                coordinates: layer.getLatLngs()
                            }, true);
                        }
                    }
                    else {
                        nameSpan.text(nameInput.val());
                        if (typeof onNameChanged === "function") {
                            onNameChanged(name);
                        }
                    }
                },
                null
            )
        },
        build_editable_popup(mainContent, id, layer, typeDisplay, allowSelfIntersection, makeRequest, onSaved, onCancelled) {
            const popupContainer = $(`
              <div>
                <div class="map-popup-group-main"></div>
                <div class="m-1">
                  <div class="map-popup-group-edit">
                    <button type="button" class="btn btn-sm btn-outline-secondary map-popup-button-edit"><i class="fas fa-edit"></i> Edit</button>
                  </div>
                  <div class="map-popup-group-saving hidden">
                    <img src="${loadingImgUrl}" alt="Saving..." style="height: 3em" /> Saving...
                  </div>
                  <div class="map-popup-group-save hidden">
                    <button type="button" class="btn btn-sm btn-outline-primary map-popup-button-save"><i class="fas fa-save"></i> Save</button>
                    <button type="button" class="btn btn-sm btn-outline-danger map-popup-button-cancel"><i class="fas fa-times"></i> <span>Reset</span></button>
                  </div>
                </div>
              </div>
            `);

            $(".map-popup-group-main", popupContainer).append(mainContent);

            const standardOpacity = layer.options.opacity;
            let originalLatLngs;

            function showGroup(suffix) {
                $(".map-popup-group-" + suffix, popupContainer).removeClass("hidden");
            }

            function hideGroup(suffix) {
                $(".map-popup-group-" + suffix, popupContainer).addClass("hidden");
            }

            function enableEdit() {
                hideGroup("edit");
                showGroup("save");

                layer.setStyle({ opacity: 1.0 });
                layer.pm.enable({ snappable: false, allowSelfIntersection: allowSelfIntersection });

                let dragging = false

                layer.on("pm:markerdragstart", function() {
                    if (dragging) {
                        // ignore multiple drag starts (left + right mouse buttons at the same time)
                        return;
                    }

                    dragging = true;
                    mouseEventsIgnore.enableIgnore();
                });

                layer.on("pm:markerdragend", function() {
                    if (!dragging) {
                        return;
                    }

                    dragging = false;
                    mouseEventsIgnore.disableIgnore();
                });
            }

            function disableEdit() {
                layer.pm.disable();
                layer.setStyle({ opacity: standardOpacity });
            }

            $(".map-popup-button-edit", popupContainer).on("click", function () {
                originalLatLngs = layer.getLatLngs();
                enableEdit();
            });

            const cancelButton = $(".map-popup-button-cancel", popupContainer);

            cancelButton.on("click", function () {
                const message = id === null
                    ? `Do you really want to delete this newly created ${typeDisplay}?`
                    : `Do you really want to stop editing and reset all changes made to this ${typeDisplay}?`;

                if (!window.confirm(message)) {
                    return;
                }

                disableEdit();
                layer.closePopup();

                if (typeof onCancelled === "function") {
                    onCancelled.call(this, originalLatLngs)
                }

                if (id === null) {
                    map.removeLayer(layer);
                }
                else {
                    if (originalLatLngs) {
                        layer.setLatLngs(originalLatLngs);
                    }

                    hideGroup("save");
                    showGroup("edit");
                }
            }.bind(this));

            $(".map-popup-button-save", popupContainer).on("click", function () {
                disableEdit();

                hideGroup("save");
                showGroup("saving");

                let coords = []

                function buildCoords(latLngs) {
                    for (let i = 0; i < latLngs.length; ++i) {
                        const value = latLngs[i];
                        if (Array.isArray(value)) {
                            buildCoords(value);
                        }
                        else {
                            coords.push(value.lat.toFixed(6) + "," + value.lng.toFixed(6));
                        }
                    }
                }

                buildCoords(layer.getLatLngs());
                const request = makeRequest(coords)

                request.then(
                    function (result) {
                        layer.closePopup();

                        if (typeof onSaved === "function") {
                            onSaved.call(this, result, originalLatLngs);
                        }

                        if (id !== null) {
                            hideGroup("saving");
                            showGroup("edit");
                        }
                    }.bind(this),
                    function () {
                        hideGroup("saving");
                        enableEdit();
                        alert(`Unable to save the ${typeDisplay}.`);
                    }.bind(this)
                );
            }.bind(this));

            if (id === null) {
                $("span", cancelButton).text("Delete");
                enableEdit();
            }

            return popupContainer[0];
        },
        build_area_popup(route) {

            const popupContainer = $(`
              <div>
                <div class="name"><i class="fas fa-drafting-compass"></i> <strong></strong></div>
              </div>
            `);

            $(".name strong", popupContainer).text(route.name);

            return popupContainer[0];
        },
        getStoredSetting(name, defaultval) {
            var val = localStorage.getItem('settings');
            if (val == null) {
                return defaultval;
            }

            var settings = JSON.parse(val);
            if (settings[name] === undefined) {
                return defaultval;
            }

            return settings[name];
        },
        updateStoredSetting(name, value) {
            var settings = {};
            var storedSettings = localStorage.getItem('settings');
            if (storedSettings != null) {
                settings = JSON.parse(storedSettings);
            }

            settings[name] = value;
            localStorage.setItem('settings', JSON.stringify(settings));
        },
        removeStoredSetting(name) {
            var settings = {};
            var storedSettings = localStorage.getItem('settings');
            if (storedSettings != null) {
                settings = JSON.parse(storedSettings);
            }

            delete settings[name];

            localStorage.setItem('settings', JSON.stringify(settings));
        },
        l_event_moveend() {
            var $this = this;
            var center = map.getCenter();
            this.updateStoredSetting('center', center.lat + ',' + center.lng);
            this.updateBounds();

            if (fetchTimeout) {
                clearTimeout(fetchTimeout);
                fetchTimeout = null;
            }

            fetchTimeout = setTimeout(function () {
                $this.map_fetch_everything();
            }, 500);
        },
        l_event_zoomed() {
            var $this = this;
            this.updateStoredSetting('zoomlevel', map.getZoom());
            this.updateBounds();

            // update gym radius dynamically
            Object.keys(leaflet_data["gyms"]).forEach(function (id) {
                leaflet_data["gyms"][id].setRadius(Math.pow((20 - map.getZoom()), 2.5));
            });

            if (fetchTimeout) {
                clearTimeout(fetchTimeout);
                fetchTimeout = null;
            }

            fetchTimeout = setTimeout(function () {
                $this.map_fetch_everything();
            }, 500);
        },
        l_event_click(e) {
            if (clickToScanActive) {
                $("#injectLocation").val(`${e.latlng.lat.toFixed(6)},${e.latlng.lng.toFixed(6)}`);
                $("#injectionModal").modal();
            }
        },
        addMouseEventPopup(marker) {
            marker.on("mouseover", function (e) {
                if (!mouseEventsIgnore.isIgnored() && !marker.isPopupOpen()) {
                    marker.keepPopupOpen = false;
                    marker.openPopup();
                }
            });

            marker.on("mouseout", function (e) {
                if (!mouseEventsIgnore.isIgnored() && !marker.keepPopupOpen) {
                    marker.closePopup();
                }
            });

            marker.on("click", function (e) {
                if (mouseEventsIgnore.isIgnored()) {
                    return;
                }

                if (marker.isPopupOpen()) {
                    marker.openPopup();
                    marker.keepPopupOpen = true;
                }
                else {
                    marker.keepPopupOpen = false;
                    marker.closePopup();
                }
            });
        },
        updateBounds(isOld) {
            if (!isOld) {
                var neLat = "neLat";
                var neLon = "neLon";
                var swLat = "swLat";
                var swLon = "swLon";
            } else {
                var neLat = "oNeLat";
                var neLon = "oNeLon";
                var swLat = "oSwLat";
                var swLon = "oSwLon";
            }

            var bounds = map.getBounds();
            this.updateStoredSetting(neLat, bounds.getNorthEast().lat);
            this.updateStoredSetting(neLon, bounds.getNorthEast().lng);
            this.updateStoredSetting(swLat, bounds.getSouthWest().lat);
            this.updateStoredSetting(swLon, bounds.getSouthWest().lng);
        },
        injectLocation() {
            $.ajax({
                type: "GET",
                url: 'send_gps?origin=' + $('#injectionWorker').val() +
                    '&coords=' + $('#injectLocation').val() +
                    '&sleeptime=' + $('#injectionSleep').val()
            });
        },
        onShapeDrawn(args) {
            if (args.shape !== "Polygon") {
                return;
            }

            const layer = args.layer;
            layer.pm.enable({ snappable: false, allowSelfIntersection: false });

            const popupContent = this.build_geofence_popup(
                null,
                "Geofence" + (Object.keys(leaflet_data.geofences).length + 1),
                layer);
            layer.bindPopup(popupContent, { className: "geofencepopup" });
            layer.openPopup();
            $(".name input", popupContent).focus();
        },
        buildUrlFilter(force = false) {
            var oSwLat = this.getStoredSetting("oSwLat", null);
            var oSwLon = this.getStoredSetting("oSwLon", null);
            var oNeLat = this.getStoredSetting("oNeLat", null);
            var oNeLon = this.getStoredSetting("oNeLon", null);

            var old = {};
            if (oSwLat && oSwLon && oNeLat && oNeLon && !force) {
                old = {
                    "oSwLat": oSwLat,
                    "oSwLon": oSwLon,
                    "oNeLat": oNeLat,
                    "oNeLon": oNeLon
                };
            }

            var timestamp = this.getStoredSetting("fetchTimestamp", null);
            if (timestamp && !force) {
                old["timestamp"] = timestamp;
            }

            var swLat = this.getStoredSetting("swLat", null);
            var swLon = this.getStoredSetting("swLon", null);
            var neLat = this.getStoredSetting("neLat", null);
            var neLon = this.getStoredSetting("neLon", null);

            var bounds = {
                "swLat": swLat,
                "swLon": swLon,
                "neLat": neLat,
                "neLon": neLon
            };

            Object.keys(old).forEach(function (key) {
                bounds[key] = old[key];
            });
            var querystring = new URLSearchParams(bounds).toString();

            // temp: update last update timestamp
            this.updateStoredSetting("fetchTimestamp", Math.floor(Date.now() / 1000))

            return "?" + querystring;
        },
        cleanup() {
            var $this = this;
            var now = moment();

            if (!cleanupInterval) {
                cleanupInterval = setInterval(this.cleanup, 14000);
            }

            Object.keys(this["mons"]).forEach(function (key) {
                var mon = $this.mons[key];
                var end = moment(mon["disappear_time"] * 1000);

                if (!now.isAfter(end))
                    return;

                map.removeLayer(leaflet_data["mons"][mon["encounter_id"]]);
                delete leaflet_data["mons"][mon["encounter_id"]];
                delete $this.mons[mon["encounter_id"]];
            });
        },
        initMap() {
            // get stored settings
            this.settings.cleanup = this.getStoredSetting("settings-cleanup", true);
            this.settings.maptiles = this.getStoredSetting("settings-maptiles", "cartodblight");
            this.settings.routes.coordinateRadius.raids = this.getStoredSetting("settings-coordinateRadius-raids", 490);
            this.settings.routes.coordinateRadius.quests = this.getStoredSetting("settings-coordinateRadius-quests", 40);
            this.settings.routes.coordinateRadius.mons = this.getStoredSetting("settings-coordinateRadius-mons", 67);
            this.settings.cellUpdateTimeout = this.getStoredSetting('settings-cellUpdateTimeout', 0);
            for (const index of Object.keys(this.layers.stat)) {
                this.layers.stat[index] = this.getStoredSetting("layer-stat-" + index, false);
            }

            // magic thingy to prevent double-loading data
            // after we initially restored settings
            // from stored settings
            this.$nextTick(function () {
                init = false;
            });

            // get stored center and zoom level if they exists
            const storedZoom = this.getStoredSetting("zoomlevel", 3);
            const storedCenter = this.getStoredSetting("center", "52.521374,13.411201");
            leaflet_data.tileLayer = L.tileLayer(this.maptiles[this.settings.maptiles].url, {
                noWrap: true,
                bounds: [
                    [-90, -180],
                    [90, 180]
                ]
            });

            map = L.map("map", {
                layers: [leaflet_data.tileLayer],
                zoomControl: false,
                updateWhenZooming: false,
                updateWhenIdle: true,
                preferCanvas: true,
                worldCopyJump: true,
                maxBounds: [
                    [-90, -180],
                    [90, 180]
                ]
            }).setView(storedCenter.split(","), storedZoom);

            // forward events to the next canvas
            mapEventForwarder = new L.eventForwarder(map);

            // create panes
            let zIndex = 390;
            const createdPanes = { };
            for (const key in layerOrders) {
                const paneName = layerOrders[key].pane;
                if (!paneName || createdPanes[paneName]) {
                    continue;
                }

                const pane = map.createPane(layerOrders[key].pane);
                pane.style.zIndex = zIndex.toString();
                createdPanes[paneName] = true;
                ++zIndex;
            }

            // add custom button
            locInjectBtn.addTo(map);

            // move zoom controls
            L.control.zoom({
                position: "bottomright"
            }).addTo(map);

            // add sidebar
            sidebar = L.control.sidebar({
                autopan: false,
                closeButton: true,
                container: "sidebar",
                position: "left",
            }).addTo(map);

            sidebar.close();

            if (setlat !== 0 && setlng !== 0) {
                L.circle([setlat, setlng], {
                    color: "blue",
                    fillColor: "blue",
                    fillOpacity: 0.5,
                    radius: 30
                }).addTo(map);

                map.setView([setlat, setlng], 20);
            }

            // configure leaflet-geoman
            map.pm.addControls({
                position: "topright",
                drawMarker: false,
                drawCircleMarker: false,
                drawPolyline: false,
                drawRectangle: false,
                drawPolygon: true,
                drawCircle: false,
                editMode: false,
                dragMode: false,
                cutPolygon: false,
                removalMode: false,
                pinningOption: false,
                snappingOption: false
            });

            map.pm.setGlobalOptions({
                snappable: false,
                allowSelfIntersection: false
            });

            map.pm.setLang(
                "custom-en",
                { buttonTitles: { drawPolyButton: "Draw new geofence" } },
                "en"
            );

            map.on("pm:drawstart", function () { mouseEventsIgnore.enableIgnore(); });
            map.on("pm:drawend", function () { mouseEventsIgnore.disableIgnore(); });
            map.on("pm:create", this.onShapeDrawn);

            map.on("zoomend", this.l_event_zoomed);
            map.on("moveend", this.l_event_moveend);
            map.on("click", this.l_event_click);
            map.on("mousedown", function () { sidebar.close(); });

            // initial load
            this.map_fetch_everything();

            // intervals
            setInterval(this.map_fetch_everything, 6000);
            if (this.settings.cleanup) {
                this.cleanup();
            }
        }
    }
});
