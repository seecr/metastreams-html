
function common_prep_form(form) {
    var _exclamation = $("#"+form.data('exclamation'));

    form.find("textarea").keyup(function(e) {
        var _control = $(this);
        _control.addClass("changes-pending");

        _exclamation.removeClass("changes-exclamation-inactive")
        _exclamation.addClass("changes-exclamation-pending");

        _exclamation.removeClass("bi-check-circle");
        _exclamation.addClass("bi-exclamation-circle-fill");

        _exclamation.prop("title", "Changes pending...");
        form.find("button[id^=btn-save-]").prop("disabled", false);
        form.find("button[id^=btn-cancel-]").prop("disabled", false);
    })
}

function common_reset_form(form) {
    form.find("textarea").removeClass("changes-pending")

    var _exclamation = $("#"+form.data('exclamation'));

    _exclamation.addClass("changes-exclamation-inactive")
    _exclamation.removeClass("changes-exclamation-pending")

    _exclamation.addClass("bi-check-circle");
    _exclamation.removeClass("bi-exclamation-circle-fill");
    _exclamation.prop("title", "");
    form.find("button[id^=btn-save-]").prop("disabled", true);
    form.find("button[id^=btn-cancel-]").prop("disabled", true);


}

function enable_tab_key(textarea) {
    textarea.on("keydown", function(e) {
        if (e.key == 'Tab') {
            e.preventDefault();
            var start = this.selectionStart;
            var end = this.selectionEnd;

            // set textarea value to: text before caret + tab + text after caret
            this.value = this.value.substring(0, start) + "    " + this.value.substring(end);

            // put caret at right position again
            this.selectionStart = this.selectionEnd = start + 1;
        }
    })
}


$(document).ready(function () {
    $(document).ajaxStart(function () { $("html").addClass("wait"); });
    $(document).ajaxStop(function () { $("html").removeClass("wait"); });
});
