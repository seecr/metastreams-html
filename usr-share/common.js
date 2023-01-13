/* begin license *
 *
 * "Metastreams Html" is a template engine based on generators, and a sequel to Slowfoot.
 * It is also known as "DynamicHtml" or "Seecr Html".
 *
 * Copyright (C) 2023 Seecr (Seek You Too B.V.) https://seecr.nl
 *
 * This file is part of "Metastreams Html"
 *
 * "Metastreams Html" is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * "Metastreams Html" is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with "Metastreams Html"; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 *
 * end license */

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