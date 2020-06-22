$(document).ready(function() {

    console.log("get_device_note ready!");

    if (jQuery.ui) {
        console.log("jQuery UI loaded nothing to do");
    } else {
        var js = document.createElement("script");
        js.type = "text/javascript";
        js.src = "https://code.jquery.com/ui/1.12.1/jquery-ui.js";
        $("head").append(js);
        $('head').append('<link rel="stylesheet" href="https://code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css" type="text/css" />');
        console.log("Added jQuery UI");
    }

    $(".device_note").bind("click", function() {
        deviceid = $(this).data('deviceid');
        click_device_notes(deviceid);
    });


});

function click_device_notes(deviceid) {
    console.log("HAAAAAAAALO");
    $.ajax({
        type: 'GET',
        url:'get_device_note',
        data:'deviceid='+ deviceid,
        success: function(msg) {
            if (msg.error == false) {
                $("<div></div>").html(msg.text).dialog({
                    modal: true,
                    width:'auto',
                    draggable: false,
                    resizable: false,
                    height: "auto",
                    title: "Note",
                    close: function() {
                        $(this).dialog('destroy').remove();
                    },
                    buttons: {
                        Ok: function () {
                            $(this).dialog("close");
                        }
                    }
                }); //end confirm dialog
            } else {
                alert(msg);
            }
        },
        error: function(msg) {
            alert(msg);
        }
    });
}
