var locinjectPane = null;
var locInjectBtn = L.easyButton({
    position: "bottomright",
    states: [{
        stateName: 'scanmode-activate',
        icon: 'fa-satellite-dish',
        title: 'Enable click-to-scan mode',
        onClick: function (btn, map) {
            clickToScanActive = true;
            L.DomUtil.addClass(map._container, 'crosshair-cursor-enabled');
            locInjectPane = map.createPane("locinject")
            locInjectPane.style.pointerEvents = 'auto';
            btn.state('scanmode-deactivate');
        }
    }, {
        stateName: 'scanmode-deactivate',
        icon: 'fa-satellite-dish',
        title: 'Disable click-to-scan mode',
        onClick: function (btn, map) {
            clickToScanActive = false;
            L.DomUtil.removeClass(map._container, 'crosshair-cursor-enabled');
            L.DomUtil.remove(locInjectPane);
            btn.state('scanmode-activate');
        }
    }]
});

function loopCoords(coordarray) {
    var returning = "";
    coordarray[0].forEach((element, index, array) => {
        returning += (element.lat + ',' + element.lng + '|');
    });
    return returning;
};

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
    var location = $(this).data("loc");
    $('#injectionModal').data('coords', location).modal();
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
var map;
var sidebar;
var init = true;
var fetchTimeout = null;
var clickToScanActive = false;
var cleanupInterval = null;
var newfences = {};
const teamNames = ['Uncontested', 'Mystic', 'Valor', 'Instinct']
const iconBasePath = "https://raw.githubusercontent.com/whitewillem/PogoAssets/resized/icons_large";

// object to hold all the markers and elements
var leaflet_data = {
    tileLayer: "",
    raids: {},
    spawns: {},
    quests: {},
    gyms: {},
    routes: {},
    prioroutes: {},
    geofences: {},
    workers: {},
    mons: {},
    monicons: {},
    cellupdates: {},
    stops: {}
};

new Vue({
    el: '#app',
    data: {
        raids: {},
        gyms: {},
        quests: {},
        stops: {},
        spawns: {},
        mons: {},
        cellupdates: {},
        fetchers: {
          workers: false,
          gyms: false,
          routes: false,
          geofences: false,
          spawns: false,
          quests: false,
          stops: false,
          mons: false,
          prioroutes: false,
          cells: false
        },
        layers: {
            stat: {
                spawns: false,
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
                geofences: {}
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
            wikimedia: {
                name: "Wikimedia",
                url: "https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}{r}.png"
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
            workerHighlight: null
        }
    },
    watch: {
        "layers.stat.gyms": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_gyms(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("raids", oldVal, newVal);
            this.changeStaticLayer("gyms", oldVal, newVal);
        },
        "layers.stat.spawns": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_spawns(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("spawns", oldVal, newVal);
        },
        "layers.stat.workers": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_workers(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("workers", oldVal, newVal);
        },
        "layers.stat.quests": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_quests(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("quests", oldVal, newVal);
        },
        "layers.stat.stops": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_stops(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("stops", oldVal, newVal);
        },
        "layers.stat.mons": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_mons(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("mons", oldVal, newVal);
        },
        "layers.stat.cellupdates": function (newVal, oldVal) {
            if (newVal && !init) {
                this.map_fetch_cells(this.buildUrlFilter(true));
            }

            this.changeStaticLayer("cellupdates", oldVal, newVal);
        },
        "layers.dyn.geofences": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("geofences");
            }
        },
        "layers.dyn.routes": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("routes");
            }
        },
        "layers.dyn.prioroutes": {
            deep: true,
            handler: function () {
                this.changeDynamicLayers("prioroutes");
            }
        },
        'settings.maptiles': function (newVal) {
            this.updateStoredSetting("settings-maptiles", newVal);
            leaflet_data.tileLayer.setUrl(this.maptiles[newVal].url);
        },
        'settings.cleanup': function (newVal) {
            this.updateStoredSetting("settings-cleanup", newVal);

            if (newVal) {
                this.cleanup();
            } else {
                clearInterval(cleanupInterval);
            }
        },
        'settings.routes.coordinateRadius': {
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
        },
        'settings.workerHighlight': function (newVal, oldVal) {
            this.updateStopHighlight();
            this.updateStoredSetting('settings-workerHighlight', newVal);
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
            urlFilter = this.buildUrlFilter();

            this.map_fetch_workers();
            this.map_fetch_gyms(urlFilter);
            this.map_fetch_routes();
            this.map_fetch_geofences();
            this.map_fetch_spawns(urlFilter);
            this.map_fetch_quests(urlFilter);
            this.map_fetch_stops(urlFilter);
            this.map_fetch_mons(urlFilter);
            this.map_fetch_prioroutes();
            this.map_fetch_cells(urlFilter);

            this.updateBounds(true);
        },
        map_fetch_workers() {
            var $this = this;

            if (this.fetchers.workers == true) {
              return;
            }

            this.fetchers.workers = true;
            axios.get("get_workers").then(function (res) {
                res.data.forEach(function (worker) {
                    var name = worker["name"];

                    if ($this["workers"][name]) {
                        leaflet_data["workers"][name].setLatLng([worker["lat"], worker["lon"]])

                        if (map.hasLayer(leaflet_data["workers"][name])) {
                            leaflet_data["workers"][name].bringToFront();
                        }
                    } else {
                        $this.workers[name] = worker;

                        leaflet_data["workers"][name] = L.circleMarker([worker['lat'], worker['lon']], {
                            radius: 7,
                            color: '#E612CB',
                            fillColor: '#E612CB',
                            weight: 1,
                            opacity: 0.9,
                            fillOpacity: 0.9
                        }).bindPopup(name);

                        $this.addMouseEventPopup(leaflet_data["workers"][name]);

                        if ($this.layers.stat.workers) {
                            leaflet_data["workers"][worker["name"]].addTo(map);
                        }
                    }
                });
            }).finally(function() {
              $this.fetchers.workers = false;
            });
        },
        map_fetch_gyms(urlFilter) {
            var $this = this;

            if (!$this.layers.stat.gyms) {
                return;
            }

            if (this.fetchers.gyms == true) {
              return;
            }

            this.fetchers.gyms = true;
            axios.get('get_gymcoords' + urlFilter).then(function (res) {
                res.data.forEach(function (gym) {
                    switch (gym['team_id']) {
                        default:
                            color = '#888';
                            break;
                        case 1:
                            color = '#0C6DFF';
                            break;
                        case 2:
                            color = '#FC0016';
                            break;
                        case 3:
                            color = '#FD830E';
                            break;
                    }

                    var skip = true;
                    if ($this["gyms"][gym["id"]]) {
                        // check if we should update an existing gym
                        if ($this["gyms"][gym["id"]]["team_id"] != gym["team_id"]) {
                            map.removeLayer(leaflet_data["gyms"][gym["id"]]);
                            delete leaflet_data["gyms"][gym["id"]];
                        } else {
                            skip = false;
                        }
                    }

                    if (skip) {
                        // store gym meta data
                        $this["gyms"][gym["id"]] = gym;

                        leaflet_data["gyms"][gym["id"]] = L.circle([gym['lat'], gym['lon']], {
                            id: gym["id"],
                            radius: Math.pow((20 - map.getZoom()), 2.5),
                            color: color,
                            fillColor: color,
                            weight: 2,
                            opacity: 1.0,
                            fillOpacity: 0.8,
                        }).bindPopup($this.build_gym_popup, {'className': 'gympopup'});

                        $this.addMouseEventPopup(leaflet_data["gyms"][gym["id"]]);

                        // only add them if they're set to visible
                        if ($this.layers.stat.gyms) {
                            leaflet_data["gyms"][gym["id"]].addTo(map);
                        }
                    }

                    if ($this["raids"][gym["id"]]) {
                        /// TODO remove past raids
                        // end time is different -> new raid
                        if ($this["raids"][gym["id"]]["end"] != gym["raid"]["end"] || gym["raid"]["end"] > (new Date().getTime() / 1000)) {
                            map.removeLayer(leaflet_data["raids"][gym["id"]]);
                            delete leaflet_data["raids"][gym["id"]];
                        }
                    }

                    if (gym["raid"] != null && gym["raid"]["end"] > (new Date().getTime() / 1000)) {
                        if (map.hasLayer(leaflet_data["raids"][gym["id"]])) {
                            return;
                        }

                        $this["raids"][gym["id"]] = gym["raid"];

                        var icon = L.divIcon({
                            html: gym["raid"]["level"],
                            className: "raidIcon",
                            iconAnchor: [-1 * (18 - map.getZoom()), -1 * (18 - map.getZoom())]
                        });

                        leaflet_data["raids"][gym["id"]] = L.marker([gym["lat"], gym["lon"]], {
                            id: gym["id"],
                            icon: icon,
                            interactive: false
                        });

                        leaflet_data["raids"][gym["id"]].addTo(map);
                    }
                });
            }).finally(function() {
              $this.fetchers.gyms = false;
            });
        },
        map_fetch_routes() {
            var $this = this;

            if (this.fetchers.routes == true) {
              return;
            }

            this.fetchers.routes = true;
            axios.get("get_route").then(function (res) {
                res.data.forEach(function (route) {
                    var group = L.layerGroup();
                    var coords = [];

                    var name = route.name;
                    var color = $this.getRandomColor();

                    if ($this.layers.dyn.routes[name]) {
                        return;
                    }

                    if (route.mode == "mon_mitm") {
                        mode = "mons";
                        cradius = $this.settings.routes.coordinateRadius.mons;
                    } else if (route.mode == "pokestops") {
                        mode = "quests";
                        cradius = $this.settings.routes.coordinateRadius.quests;
                    } else if (route.mode == "raids_mitm") {
                        mode = "raids";
                        cradius = $this.settings.routes.coordinateRadius.raids;
                    } else {
                        mode = route.mode;
                    }

                    let stack = []
                    let processedCells = {};

                    route.coordinates.forEach(function (coord) {
                        circle = L.circle(coord, {
                            pane: "routes",
                            radius: cradius,
                            color: color,
                            fillColor: color,
                            fillOpacity: 1,
                            weight: 1,
                            opacity: 0.4,
                            fillOpacity: 0.1
                        });

                        circle.addTo(group);
                        coords.push(circle);

                        if (mode == "raids") {
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
                            interactive: false
                          }).addTo(group);

                          while (stack.length > 0) {
                            const cell = stack.pop();
                            const neighbors = cell.getNeighbors()
                            neighbors.forEach(function (ncell, index) {
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
                                      interactive: false
                                    }).addTo(group);
                                    break
                                  }
                                }
                              }
                            })
                          }
                        }
                    });

                    var geojson = {
                        "type": "LineString",
                        "coordinates": $this.convertToLonLat(route.coordinates)
                    }

                    // add route to layergroup
                    L.geoJSON(geojson, {
                        pane: "routes",
                        style: {
                            "color": color,
                            "weight": 2,
                            "opacity": 0.4
                        }
                    }).addTo(group);

                    // add layergroup to management object
                    leaflet_data["routes"][name] = group;

                    var settings = {
                        "show": $this.getStoredSetting("layers-dyn-routes-" + name, false),
                        "mode": mode
                    };

                    $this.$set($this.layers.dyn.routes, name, settings);
                });
            }).finally(function() {
              $this.fetchers.routes = false;
            });
        },
        map_fetch_prioroutes() {
            var $this = this;

            if (this.fetchers.prioroutes == true) {
              return;
            }

            this.fetchers.prioroutes = true;
            axios.get("get_prioroute").then(function (res) {
                res.data.forEach(function (route) {
                    var group = L.layerGroup();
                    var coords = [];

                    var name = route.name;

                    if ($this.layers.dyn.prioroutes[name]) {
                        map.removeLayer(leaflet_data["prioroutes"][name]);
                    }

                    if (route.mode == "mon_mitm" || route.mode == "iv_mitm") {
                        mode = "mons";
                        cradius = $this.settings.routes.coordinateRadius.mons;
                    } else if (route.mode == "pokestops") {
                        mode = "quests";
                        cradius = $this.settings.routes.coordinateRadius.quests;
                    } else if (route.mode == "raids_mitm") {
                        mode = "raids";
                        cradius = $this.settings.routes.coordinateRadius.raids;
                    }

                    var maxcolored = 10;
                    var color = "#BBB";

                    var linecoords = [];

                    // only display first 10 entries of the queue
                    const now = Math.round((new Date()).getTime() / 1000);
                    route.coordinates.slice(0, 14).forEach(function (coord, index) {
                        let until = coord.timestamp - now;

                        if (until < 0) {
                            var hue = 0;
                            var sat = 100;
                        } else {
                            var hue = 120;
                            var sat = (index * 100) / 15;
                        }

                        var color = `hsl(${hue}, ${sat}%, 50%)`;

                        circle = L.circle([coord.latitude, coord.longitude], {
                            ctimestamp: coord.timestamp,
                            radius: cradius,
                            color: color,
                            fillColor: color,
                            fillOpacity: 1,
                            weight: 1,
                            opacity: 0.8,
                            fillOpacity: 0.5
                        }).bindPopup($this.build_prioq_popup);

                        circle.addTo(group);
                        coords.push(circle);
                        linecoords.push([coord.latitude, coord.longitude]);
                    });

                    var geojson = {
                        "type": "LineString",
                        "coordinates": $this.convertToLonLat(linecoords)
                    }

                    // add route to layergroup
                    L.geoJSON(geojson, {
                        //pane: "routes",
                        style: {
                            "color": "#000000",
                            "weight": 2,
                            "opacity": 0.2
                        }
                    }).addTo(group);

                    // add layergroup to management object
                    leaflet_data["prioroutes"][name] = group;

                    var settings = {
                        "show": $this.getStoredSetting("layers-dyn-prioroutes-" + name, false),
                        "mode": mode
                    };

                    $this.$set($this.layers.dyn.prioroutes, name, settings);
                });
            }).finally(function() {
              $this.fetchers.prioroutes = false;
            });
        },
        map_fetch_spawns(urlFilter) {
            var $this = this;

            if (!$this.layers.stat.spawns) {
                return;
            }

            if (this.fetchers.spawns == true) {
              return;
            }

            this.fetchers.spawns = true;
            axios.get('get_spawns' + urlFilter).then(function (res) {
                res.data.forEach(function (spawn) {
                    if (spawn['endtime'] !== null) {
                        var endsplit = spawn['endtime'].split(':');
                        var endMinute = parseInt(endsplit[0]);
                        var endSecond = parseInt(endsplit[1]);
                        var despawntime = moment();
                        var now = moment();

                        if (spawn['spawndef'] == 15) {
                            var timeshift = 60;
                        } else {
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

                        timeformat = 'YYYY-MM-DD HH:mm:ss';
                        if (now.isBetween(spawntime, despawntime)) {
                            var color = "green";
                        } else if (spawntime.isAfter(now)) {
                            var color = "blue";
                        }
                    } else {
                        var color = "red";
                    }

                    var skip = true;
                    if ($this["spawns"][spawn["id"]]) {
                        // check if we should update an existing spawn
                        if ($this["spawns"][spawn["id"]]["endtime"] === null && spawn["endtime"] !== null) {
                            map.removeLayer(leaflet_data["spawns"][spawn["id"]]);
                            delete leaflet_data["spawns"][spawn["id"]];
                        } else {
                            skip = false;
                        }
                    }

                    if (skip) {
                        // store spawn meta data
                        $this["spawns"][spawn["id"]] = spawn;

                        leaflet_data["spawns"][spawn["id"]] = L.circle([spawn['lat'], spawn['lon']], {
                            radius: 2,
                            color: color,
                            fillColor: color,
                            weight: 1,
                            opacity: 0.7,
                            fillOpacity: 0.5,
                            id: spawn["id"]
                        }).bindPopup($this.build_spawn_popup, {'className': 'spawnpopup'});

                        $this.addMouseEventPopup(leaflet_data["spawns"][spawn["id"]]);

                        // only add them if they're set to visible
                        if ($this.layers.stat.spawns) {
                            leaflet_data["spawns"][spawn["id"]].addTo(map);
                        }
                    }
                });
            }).finally(function() {
              $this.fetchers.spawns = false;
            });
        },
        map_fetch_quests(urlFilter) {
            var $this = this;

            if (!$this.layers.stat.quests) {
                return;
            }

            if (this.fetchers.quests == true) {
              return;
            }

            this.fetchers.quests = true;
            axios.get("get_quests" + urlFilter).then(function (res) {
                res.data.forEach(function (quest) {
                    if ($this.quests[quest["pokestop_id"]]) {
                        return;
                    }

                    $this.quests[quest["pokestop_id"]] = quest;

                    leaflet_data["quests"][quest["pokestop_id"]] = L.marker([quest['latitude'], quest['longitude']], {
                        id: quest["pokestop_id"],
                        virtual: true,
                        icon: $this.build_quest_small(quest['quest_reward_type_raw'], quest['item_id'], quest['pokemon_id'], quest['pokemon_form'], quest['pokemon_asset_bundle_id'], quest['pokemon_costume'])
                    }).bindPopup($this.build_quest_popup, {"className": "questpopup"});

                    $this.addMouseEventPopup(leaflet_data["quests"][quest["pokestop_id"]]);

                    if ($this.layers.stat.quests) {
                        leaflet_data["quests"][quest["pokestop_id"]].addTo(map);
                    }
                });
            }).finally(function() {
              $this.fetchers.quests = false;
            });
        },
        map_fetch_stops(urlFilter) {
            var $this = this;
            if (!$this.layers.stat.stops) {
                return;
            }

            if (this.fetchers.stops == true) {
              return;
            }

            this.fetchers.stops = true;
            axios.get("get_stops" + urlFilter).then(function (res) {
                res.data.forEach(function (stop) {
                    var stop_id = stop["pokestop_id"];
                    if ($this.stops[stop_id]) {
                        if ($this.stops[stop_id]["last_updated"] === stop["last_updated"]) {
                            return;
                        }

                        map.removeLayer(leaflet_data["stops"][stop_id]);
                        delete leaflet_data["stops"][stop_id];
                    }
                    var color = $this.getStopColor(stop);
                    $this.stops[stop_id] = stop;
                    leaflet_data["stops"][stop_id] = L.circle([stop["latitude"], stop["longitude"]], {
                        radius: 8,
                        color: color,
                        fillColor: color,
                        weight: 1,
                        opacity: 0.7,
                        fillOpacity: 0.5,
                        id: stop_id
                    }).bindPopup($this.build_stop_popup, {"className": "stoppopup"});
                    $this.addMouseEventPopup(leaflet_data["stops"][stop_id]);
                    if ($this.layers.stat.stops) {
                        leaflet_data["stops"][stop_id].addTo(map);
                    }
                });
            }).finally(function() {
              $this.fetchers.stops = false;
            });
        },
        map_fetch_geofences() {
            var $this = this;

            if (this.fetchers.geofences == true) {
              return;
            }

            this.fetchers.geofences = true;
            axios.get('get_geofence').then(function (res) {
                res.data.forEach(function (geofence) {
                    var group = L.layerGroup();

                    // meta data for management
                    var name = geofence.name;

                    if ($this.layers.dyn.geofences[name]) {
                        return;
                    }

                    // add geofence to layergroup
                    var group = L.polygon(geofence.coordinates, {pane: "geofences",})
                        .setStyle({
                            "color": $this.getRandomColor(),
                            "weight": 2,
                            "opacity": 0.5
                        })
                        .addTo(map);

                    // add layergroup to management object
                    leaflet_data["geofences"][name] = group;

                    var settings = {
                        "show": $this.getStoredSetting("layers-dyn-geofences-" + name, false),
                    };

                    $this.$set($this.layers.dyn.geofences, name, settings);
                });
            }).finally(function() {
              $this.fetchers.geofences = false;
            });
        },
        map_fetch_mons(urlFilter) {
            var $this = this;

            if (!$this.layers.stat.mons) {
                return;
            }

            if (this.fetchers.mons == true) {
              return;
            }

            this.fetchers.mons = true;
            axios.get('get_map_mons' + urlFilter).then(function (res) {
                res.data.forEach(function (mon) {

                    var noskip = true;
                    if ($this["mons"][mon["encounter_id"]]) {
                        if ($this["mons"][mon["encounter_id"]]["last_modified"] != mon["last_modified"]) {
                            map.removeLayer(leaflet_data["mons"][mon["encounter_id"]]);
                            delete leaflet_data["mons"][mon["encounter_id"]];
                        } else {
                            noskip = false;
                        }
                    }

                    if (noskip) {
                        // store meta data
                        $this["mons"][mon["encounter_id"]] = mon;

                        if (leaflet_data["monicons"][mon["mon_id"]]) {
                            var icon = leaflet_data["monicons"][mon["mon_id"]];
                        } else {
                            var form = mon["form"] == 0 ? "00" : mon["form"];
                            var image = `${iconBasePath}/pokemon_icon_${String.prototype.padStart.call(mon["mon_id"], 3, 0)}_${form}.png`;
                            var icon = L.icon({
                                iconUrl: image,
                                iconSize: [40, 40],
                            });

                            leaflet_data["monicons"][mon["mon_id"]] = icon;
                        }

                        leaflet_data["mons"][mon["encounter_id"]] = L.marker([mon["latitude"], mon["longitude"]], {
                            id: mon["encounter_id"],
                            virtual: true,
                            icon: icon
                        }).bindPopup($this.build_mon_popup, {"className": "monpopup"});

                        $this.addMouseEventPopup(leaflet_data["mons"][mon["encounter_id"]]);

                        // only add them if they're set to visible
                        if ($this.layers.stat.mons) {
                            leaflet_data["mons"][mon["encounter_id"]].addTo(map);
                        }
                    }
                });
            }).finally(function() {
              $this.fetchers.mons = false;
            });
        },
        map_fetch_cells(urlFilter) {
            var $this = this;

            if (!$this.layers.stat.cellupdates) {
                return;
            }

            if (this.fetchers.cells == true) {
              return;
            }

            this.fetchers.cells = true;
            axios.get('get_cells' + urlFilter).then(function (res) {
                const now = Math.round((new Date()).getTime() / 1000);

                res.data.forEach(function (cell) {
                    var noskip = true;
                    if ($this.cellupdates[cell.id]) {
                        if ($this.cellupdates[cell.id].updated != cell.updated) {
                            map.removeLayer(leaflet_data.cellupdates[cell.id]);
                            delete leaflet_data.cellupdates[cell.id];
                        } else {
                            noskip = false;
                        }
                    }

                    if (noskip) {
                        $this.cellupdates[cell.id] = cell;

                        leaflet_data.cellupdates[cell.id] = L.polygon(cell.polygon, {id: cell.id})
                            .setStyle($this.getCellStyle(now, cell.updated))
                            .bindPopup($this.build_cell_popup, {className: "cellpopup"})
                            .addTo(map);
                    }
                })
            }).finally(function() {
              $this.fetchers.cells = false;
            });
        },
        updateStopHighlight() {
            for (var stopID of Object.keys(this.stops)) {
                if (leaflet_data["stops"][stopID]) {
                    var color = this.getStopColor(this.stops[stopID]);
                    leaflet_data["stops"][stopID].setStyle({
                        color: color,
                        fillColor: color
                    });
                }
            }
        },
        changeDynamicLayers(type) {
            for (k in this.layers.dyn[type]) {
                tlayer = this.layers.dyn[type][k];
                this.updateStoredSetting("layers-dyn-" + type + "-" + k, tlayer.show);

                if (tlayer.show == true && !map.hasLayer(leaflet_data[type][k])) {
                    map.addLayer(leaflet_data[type][k]);
                } else if (tlayer.show == false && map.hasLayer(leaflet_data[type][k])) {
                    map.removeLayer(leaflet_data[type][k]);
                }
            }
        },
        changeStaticLayer(name, oldstate, newState) {
            if (oldstate === true) {
                Object.keys(leaflet_data[name]).forEach(function (key) {
                    map.removeLayer(leaflet_data[name][key]);
                });
            } else {
                Object.keys(leaflet_data[name]).forEach(function (key) {
                    map.addLayer(leaflet_data[name][key]);
                });
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
        getStopColor(stop) {
            var color = stop["has_quest"] ? "blue" : "red";
            if (this.settings.workerHighlight && stop["visited_by"]) {
                color = stop["visited_by"].includes(this.settings.workerHighlight) ? 'green' : color;
            }
            return color;
        },
        getRandomColor() {
            // generates only dark colors for better contrast
            var letters = '0123456789'.split('');
            var color = '#';
            for (var i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 10)];
            }
            return color;
        },
        getPercentageColor(percentage) {
            var r, g, b = 0;

            if (percentage < 50) {
                r = 255;
                g = Math.round(5.1 * percentage);
            } else {
                g = 255;
                r = Math.round(510 - 5.10 * percentage);
            }

            var h = r * 0x10000 + g * 0x100 + b * 0x1;
            return "#" + ("000000" + h.toString(16)).slice(-6);
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
            var time = moment(marker.options.ctimestamp * 1000);
            return `Due: ${time.format("YYYY-MM-DD HH:mm:ss")} (${marker.options.ctimestamp})`;
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
          <div class="image" style="background: url(${image}) center center no-repeat;"></div>
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

            var visited = "";
            if (stop['visited_by']) {
                visited = `<div class="visited"><i class="fa fa-shoe-prints"></i> Visited by workers: <strong>${stop['visited_by'].join(', ')}</strong></div>`
            }

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
          ${visited}
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
          <div class="image" style="background: url(${gym["img"]}) center center no-repeat;"></div>
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
         <button id="sendworker" class="btn btn-outline-secondary btn-sm" data-loc="${gym["latitude"]},${gym["longitude"]}"><i class="fas fa-satellite-dish"></i> Send worker here</button>
        </div>`;
        },
        build_spawn_popup(marker) {
            spawn = this.spawns[marker.options.id];

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
            <div class="spawnFirstDetection"><i class="fas fa-baby"></i> First seen: <strong>${spawn["first_detection"]}</strong></div>
            <div class="timestamp"><i class="fas fa-eye"></i> <abbr title="This is the time a mon has been seen on this spawnpoint.">Last mon seen</abbr>: <strong>${lastMon}</strong></div>
            <div class="timestamp"><i class="fa fa-clock"></i> <abbr title="The timestamp of the last time this spawnpoint's despawn time has been confirmed.">Last confirmation</abbr>: <strong>${spawn["lastscan"]}</strong></div>
            <div class="spawnType"><i class="fa fa-wrench"></i> Type: <strong>${type || "Unknown despawn time"}</strong></div>
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
        <button id="sendworker" class="btn btn-outline-secondary btn-sm" data-loc="${mon["latitude"]},${mon["longitude"]}"><i class="fas fa-satellite-dish"></i> Send worker here</button>
        <div class="monImg" style="background-image: url(${image}); background-size: 100%"></div>
        </div>
      `;
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
                marker.keepPopupOpen = false;
                marker.openPopup();
                marker.popupOpen = true;
            });

            marker.on("mouseout", function (e) {
                if (!marker.keepPopupOpen) {
                    marker.closePopup();
                    marker.popupOpen = false;
                }
            });

            marker.on("click", function (e) {
                if (marker.popupOpen) {
                    marker.openPopup();
                    marker.keepPopupOpen = true;
                } else {
                    marker.keepPopupOpen = false;
                    marker.closePopup();
                    marker.popupOpen = false;
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
        convertToLonLat(coords) {
            lonlat = []
            coords.forEach(function (coord) {
                lonlat.push([coord[1], coord[0]]);
            });
            return lonlat;
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
            this.settings.routes.coordinateRadius.raids = this.getStoredSetting('settings-coordinateRadius-raids', 490);
            this.settings.routes.coordinateRadius.quests = this.getStoredSetting('settings-coordinateRadius-quests', 40);
            this.settings.routes.coordinateRadius.mons = this.getStoredSetting('settings-coordinateRadius-mons', 67);
            this.settings.workerHighlight = this.getStoredSetting('settings-workerHighlight');
            for (index of Object.keys(this.layers.stat)) {
                this.layers.stat[index] = this.getStoredSetting("layer-stat-" + index, false);
            }

            // magic thingy to prevent double-loading data
            // after we initially restored settings
            // from stored settings
            this.$nextTick(function () {
                init = false;
            });

            // get stored center and zoom level if they exists
            const storedZoom = this.getStoredSetting('zoomlevel', 3);
            const storedCenter = this.getStoredSetting('center', '52.521374,13.411201');
            leaflet_data.tileLayer = L.tileLayer(this.maptiles[this.settings.maptiles].url, {
                noWrap: true,
                bounds: [
                    [-90, -180],
                    [90, 180]
                ]
            });

            map = L.map('map', {
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
            }).setView(storedCenter.split(','), storedZoom);

            // add custom button
            locInjectBtn.addTo(map);

            // extra panes to make sure routes and
            // geofences are below everything else
            map.createPane("geofences");
            map.createPane("routes");

            // move zoom controls
            L.control.zoom({
                position: 'bottomright'
            }).addTo(map);

            // add sidebar
            sidebar = L.control.sidebar({
                autopan: false,
                closeButton: true,
                container: "sidebar",
                position: "left",
            }).addTo(map);

            sidebar.close();

            if (setlat != 0 && setlng != 0) {
                var circle = L.circle([setlat, setlng], {
                    color: 'blue',
                    fillColor: 'blue',
                    fillOpacity: 0.5,
                    radius: 30
                }).addTo(map);

                map.setView([setlat, setlng], 20);
            }

            map.on('zoomend', this.l_event_zoomed);
            map.on('moveend', this.l_event_moveend);
            map.on('click', this.l_event_click);
            map.on('mousedown', function () {
                sidebar.close();
            });

            var editableLayers = new L.FeatureGroup();
            map.addLayer(editableLayers);

            var options = {
                position: 'topright',
                draw: {
                    polyline: false,
                    polygon: {
                        allowIntersection: false,
                        drawError: {
                            color: '#e1e100',
                            message: '<strong>Oh snap!<strong> you can\'t draw that!'
                        },
                        shapeOptions: {
                            color: '#ac00e6'
                        }
                    },
                    circle: false,
                    circlemarker: false,
                    rectangle: false,
                    line: false,
                    marker: false,
                },
                edit: {
                    featureGroup: editableLayers,
                    remove: false
                }
            };

            var drawControl = new L.Control.Draw(options);
            map.addControl(drawControl);

            map.on(L.Draw.Event.CREATED, function (e) {
                var type = e.layerType;
                var layer = e.layer;

                var fencename = prompt("Please enter name of fence", "");
                coords = loopCoords(layer.getLatLngs())
                newfences[layer] = fencename
                layer.bindPopup('<b>' + fencename + '</b><br><a href=savefence?name=' + encodeURI(fencename) + '&coords=' + coords + '>Save to MAD</a>');
                editableLayers.addLayer(layer);
                layer.openPopup();
            });

            map.on('draw:edited', function (e) {
                var layers = e.layers;
                layers.eachLayer(function (layer) {
                    coords = loopCoords(layer.getLatLngs())
                    layer._popup.setContent('<b>' + newfences[layer] + '</b><br><a href=savefence?name=' + encodeURI(newfences[layer]) + '&coords=' + coords + '>Save to MAD</a>')
                    layer.openPopup();
                });
            });

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
