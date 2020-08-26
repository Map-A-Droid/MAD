function loadingBlockUI(message) {
    $.fn.center = function () {
        this.css("position", "absolute");
        this.css("top", ($(window).height() - this.height()) / 2 + $(window).scrollTop() + "px");
        this.css("left", ($(window).width() - this.width()) / 2 + $(window).scrollLeft() + "px");
        return this;
    }

$.blockUI({css: {
            height: 'auto',
            textAlign: 'center',
            width: 'auto'
		}, message: '<img src="/static/loading.gif" width="100px" /><br/><h2  style="margin-left: 20px;margin-right: 20px;">' + message + '</h2>' })
            $('.blockUI.blockMsg').center();
}