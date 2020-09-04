"use strict";

// Allows forwarding events from one pane to another (with preferCanvas=true)
// See https://github.com/Leaflet/Leaflet/issues/6205 for details.
// Originally based on https://github.com/danwild/leaflet-event-forwarder but almost rewritten completely since.
const EventForwarder = L.Class.extend({

    initialize: function (map) {
        this._map = map;
        this._isDraggingMap = false;
        this._previousMousePane = null;
        this.isEnabled = true;

        map.on("dragstart", this._onDragStart, this);
        map.on("dragend", this._onDragEnd, this);

        L.DomEvent.on(map, "click", this._preventReentrancy(this._onClick), this);
        L.DomEvent.on(map, "mouseout", this._preventReentrancy(this._onMouseOut), this);
        L.DomEvent.on(map, "mousemove", this._preventReentrancy(this._onMouseMove), this);
    },

    _preventReentrancy(fn) {
        let reentrancyGuard = false;

        return function() {
            if (reentrancyGuard) {
                return;
            }

            reentrancyGuard = true;
            try {
                return fn.apply(this, arguments);
            }
            finally {
                reentrancyGuard = false;
            }
        }.bind(this);
    },

    _onDragStart: function () {
        this._isDraggingMap = true;
    },

    _onDragEnd: function () {
        this._isDraggingMap = false;
    },

    _onClick: function (event) {
        if (this.isEnabled) {
            this._propagateEvent(event);
        }
    },

    _onMouseOut: function (event) {
        if (!this.isEnabled || this._isDraggingMap || this._previousMousePane === null) {
            return;
        }

        const originalTarget = event.originalEvent.target;
        if (originalTarget === this._previousMousePane)
            return;

        this._previousMousePane.dispatchEvent(new MouseEvent("mouseout", event.originalEvent));
        this._previousMousePane = null;

        this._addAndRemoveMapClasses("leaflet-grab", "leaflet-interactive");
    },

    _onMouseMove: function (event) {
        if (!this.isEnabled || this._isDraggingMap) {
            return;
        }

        const mousePane = this._propagateEvent(event);

        if (this._previousMousePane === mousePane) {
            return;
        }

        if (this._previousMousePane !== null) {
            this._previousMousePane.dispatchEvent(new MouseEvent("mouseout", event.originalEvent));
        }

        this._previousMousePane = mousePane;

        // fix cursor
        if (mousePane !== null) {
            this._addAndRemoveMapClasses("leaflet-interactive", "leaflet-grab");
        }
        else {
            this._addAndRemoveMapClasses("leaflet-grab", "leaflet-interactive");
        }
    },

    _addAndRemoveMapClasses(classToAdd, classToRemove) {
        const containerClasses = this._map.getContainer().classList;

        if (!containerClasses.contains(classToAdd)) {
            containerClasses.add(classToAdd);
        }

        containerClasses.remove(classToRemove);
    },

    _propagateEvent(event) {
        const originalTarget = event.originalEvent.target;
        if (originalTarget.nodeName.toLowerCase() !== "canvas" || originalTarget.classList.contains("leaflet-interactive")) {
            return originalTarget;
        }

        const removedTargets = [];

        function removeTarget(target) {
            removedTargets.push({ target: target, oldPointerEvents: target.style.pointerEvents });
            target.style.pointerEvents = "none";
        }

        try {
            let previousTarget = originalTarget;

            // propages the event until we find an interactive layer
            while (true) {
                removeTarget(previousTarget);

                const nextTarget = document.elementFromPoint(event.originalEvent.clientX, event.originalEvent.clientY);

                if (nextTarget === null
                || nextTarget.classList.contains("leaflet-container") // reached the map itself
                || nextTarget.nodeName.toLowerCase() === "body") {
                    return null;
                }

                const newEvent = new MouseEvent(event.type, event.originalEvent);
                if (!nextTarget.dispatchEvent(newEvent) || nextTarget.classList.contains("leaflet-interactive")) {
                    return nextTarget;
                }

                previousTarget = nextTarget;
            }
        }
        finally {
            for (const removedTarget of removedTargets) {
                removedTarget.target.style.pointerEvents = removedTarget.oldPointerEvents;
            }
        }
    }

});

L.eventForwarder = function (map) {
    return new EventForwarder(map);
};
