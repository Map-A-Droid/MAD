// CONVERT_TO_NONE = ["geofence_excluded", "pool", "cool_down_sleep", "reboot"];

function get_save_data() {
    save_data = {};
    $(".form-control").each(function() {
        var obj = $(this);
        var name = obj.attr('name');
        value = null;
        if(obj.data('skip')) {
            return;
        }
        if(obj.data('callback')) {
            value = eval(obj.data('callback') + '()');
        } else if(obj.is('select')) {
            value = obj.children("option:selected").val();
            if(value == 'None') {
                value = null;
            }
        } else if(obj.is('input')) {
            value = obj.val();
        }
        if(value != null && value.length == 0)
            value = null;
        default_val = obj.data('default');
        if((default_val == 'None' || default_val.length == 0) && value == null) {
            return;
        }
        if(value == obj.data('default')) {
            return;
        }
        if(obj.attr('setting') == 'true') {
            if(!save_data.hasOwnProperty('settings')) {
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
        url : uri,
        data : JSON.stringify(save_data),
        type : method,
        contentType : 'application/json',
        success: function(data, status, xhr) {
          if(xhr.status < 400)
            window.location.replace(redirect);
        },
        error: function(data, status, xhr) {
            $("label[for]").removeClass('btn-danger');
            if(data['responseJSON'] != undefined) {
                $.each(data['responseJSON']['missing'], function() {
                    var elem = $("label[for="+ this +"]");
                    elem[0].innerHTML = elem.attr('for') +' - Required Field';
                    elem.addClass('btn-danger');
                });
                $.each(data['responseJSON']['invalid'], function() {
                    var field = this[0];
                    var expected = this[1];
                    var elem = $("label[for="+ field +"]");
                    elem[0].innerHTML = elem.attr('for') +' - Expected '+ expected;
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