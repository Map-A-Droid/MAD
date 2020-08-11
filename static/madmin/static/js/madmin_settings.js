// CONVERT_TO_NONE = ["geofence_excluded", "pool", "cool_down_sleep", "reboot"];

var ItemData = [{
   id: 1,
   text: 'Poké Ball (#1)',
}, {
   id: 2,
   text: 'Great Ball (#2)',
}, {
   id: 3,
   text: 'Ultra Ball (#3)',
}, {
   id: 101,
   text: 'Potion (#101)',
}, {
   id: 102,
   text: 'Super Potion (#102)',
}, {
   id: 103,
   text: 'Hyper Potion (#103)',
}, {
   id: 104,
   text: 'Max Potion (#104)',
}, {
   id: 201,
   text: 'Revive (#201)',
}, {
   id: 202,
   text: 'Max Revive (#202)',
}, {
   id: 301,
   text: 'Lucky Egg (#301)',
}, {
   id: 401,
   text: 'Incense (#401)',
}, {
   id: 501,
   text: 'Normal Lure Module (#501)',
}, {
   id: 502,
   text: 'Glacial Lure Module (#502)',
}, {
   id: 503,
   text: 'Mossy Lure Module (#503)',
}, {
   id: 504,
   text: 'Magnetic Lure Module (#504)',
}, {
   id: 701,
   text: 'Razz Berry (#701)',
}, {
   id: 703,
   text: 'Nanab Berry (#703)',
}, {
   id: 705,
   text: 'Pinap Berry (#705)',
}, {
   id: 706,
   text: 'Golden Razz Berry (#706)',
}, {
   id: 708,
   text: 'Silver Pinap Berry (#708)',
}, {
   id: 709,
   text: 'Poffin (#709)',
}, {
   id: 801,
   text: 'Upgraded Camera (#801)',
}, {
   id: 901,
   text: 'Egg Incubators (#901)',
}, {
   id: 902,
   text: 'Limited Egg Incubators (#902)',
}, {
   id: 903,
   text: 'Super Egg Incubators (#903)',
}, {
   id: 1101,
   text: 'Sun Stone (#1101)',
}, {
   id: 1102,
   text: 'Kings Rock (#1102)',
}, {
   id: 1103,
   text: 'Metal Coat (#1103)',
}, {
   id: 1104,
   text: 'Dragon Scale (#1104)',
}, {
   id: 1105,
   text: 'Up-Grade (#1105)',
}, {
   id: 1106,
   text: 'Sinnoh Stone (#1106)',
}, {
   id: 1107,
   text: 'Unova Stone (#1107)',
}, {
   id: 1201,
   text: 'Fast TM (#1201)',
}, {
   id: 1202,
   text: 'Charged TM (#1202)',
}, {
   id: 1203,
   text: 'Elite Fast TM (#1203)',
}, {
   id: 1204,
   text: 'Elite Charged TM (#1204)',
}, {
   id: 1301,
   text: 'Rare Candy (#1301)',
}, {
   id: 1401,
   text: 'Raid Pass (#1401)',
}, {
   id: 1402,
   text: 'Premium Raid Pass (#1402)',
}, {
   id: 1403,
   text: 'EX Raid Pass (#1403)',
}, {
   id: 1404,
   text: 'Star piece (#1404)',
}, {
   id: 1408,
   text: 'Remote Raid Pass (#1408)',
}, {
   id: 1501,
   text: 'Map Fragment (#1501)',
}, {
   id: 1502,
   text: 'Leader Map Radar (#1502)',
}, {
   id: 1503,
   text: 'Super Leader Map Radar (#1503)',
}, {
   id: 1600,
   text: 'Global Ticket (#1600)',
}

];

function get_save_data() {
    save_data = {};
    $(".form-control").each(function () {
        var obj = $(this);
        var name = obj.attr('name');
        var default_val = obj.data('default');
        value = null;
        if (obj.data('skip')) {
            return;
        }

        if (obj.data('callback')) {
            value = eval(obj.data('callback') + '()');
        } else if (obj.hasClass("select2-hidden-accessible")) {
            value = obj.val().toString();
        } else if (obj.is('select')) {
            value = obj.children("option:selected").val();
            if (value == 'None') {
                value = null;
            }
        } else if (obj.is('input')) {
          if(obj.prop('type') == 'checkbox') {
            value = !obj.parent().hasClass('off');
            default_val = $(obj.parent().children()[0]).data('default');
          } else {
            value = obj.val();
          }
        }
        if (value != null && value.length == 0)
            value = null;
        if ((default_val == 'None' || default_val.length == 0) && value == null) {
            return;
        }
        if (value == obj.data('default')) {
            return;
        }
        if (obj.attr('setting') == 'true') {
            if (!save_data.hasOwnProperty('settings')) {
                save_data['settings'] = {};
            }
            save_data['settings'][name] = value;
        } else {
            save_data[name] = value;
        }
    });
    return save_data;
}

function isEmptyObj(object) {
    for (var key in object) {
        if (object.hasOwnProperty(key)) {
            return false;
        }
    }
}


function process_api_request(uri, method, redirect) {
    $.ajax({
        url: uri,
        data: JSON.stringify(save_data),
        type: method,
        contentType: 'application/json',
        success: function (data, status, xhr) {
            if (xhr.status < 400)
                window.location.replace(redirect);
        },
        error: function (data, status, xhr) {
            $("label[for]").removeClass('btn-danger');
            if (data['responseJSON'] != undefined) {
                $.each(data['responseJSON']['missing'], function () {
                    var elem = $("label[for=" + this + "]");
                    elem[0].innerHTML = elem.attr('for') + ' - Required Field';
                    elem.addClass('btn-danger');
                });
                $.each(data['responseJSON']['invalid'], function () {
                    var field = this[0];
                    var expected = this[1];
                    var elem = $("label[for=" + field + "]");
                    elem[0].innerHTML = elem.attr('for') + ' - Expected ' + expected;
                    elem.addClass('btn-danger');
                });
                $.unblockUI();
                alert('One or more fields failed validation');
            } else {
                $.unblockUI();
                alert('Unable to save the {{ subtab }}.  An unknown error occurred');
            }
        }
    });
}
