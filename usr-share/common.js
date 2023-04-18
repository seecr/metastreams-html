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


import {get_tester} from "./autotest.js"
let test = get_tester("query2");

import {validate} from "./aproba.js";


export function form_data(form) {
    return form.serializeArray().reduce((a, {name, value}) => {a[name] = value; return a;}, {});
}


test(function form_data_as_key_values() {
    $('html').append(
        $('<form>').append(
            $('<input name="one" value="11">'),
            $('<input name="two" value="22">'),
        )
    );
    test.eq({one: '11', two: '22'}, form_data($('form')));
});


export function common_prep_form(form) {
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

export function common_reset_form(form) {
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

export function enable_tab_key(textarea) {
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


//
// Call a Python function in a .sf, marked with callpy.jscallable.
//
export function call_py(funcname, kwargs = {}, done) {
    kwargs['call_py']=funcname;
    let url = new URL(location);
    const response = $.get(url.origin + url.pathname, kwargs);
    response.done(data => {
        // I did not find a Headers parser. This one support only one value per key,
        // but that is enough for Python arguments.
        let kwargs = Object.fromEntries(
                response.getAllResponseHeaders()
                .split("\r\n")
                .map(line => line.split(": "))
                .filter(([key, value]) => key.startsWith('py-arg-'))
                .map(([key, value]) => [key.substring(7,99), parseFloat(value)]));
        done(data, kwargs);
    })
    .fail(function(m) {
        console.error("ERROR calling", funcname, '(', kwargs, '):', m);
    });
}


export function replace_content(node, data) {
    /* replace data in html page, executing call_js functions */
    validate("OS", arguments);
    let n = $(node);
    node.empty().append(data);
    call_js_all(node);
}


/*
 * Support for calling Javascript from Python and v.v.
 */
export function call_js_all(element, self) {
    /*
     * Python can call Javascript with:
     *      with tag('div', **call_js('a_module.a_js_function', arg1=42)):
     *
     * => The function 'a_js_function' from module 'a_module' is executed on document.ready.
     */
    let root;
    if (element == undefined)
        root = $('*')
    else
        root = $(element);

    if (self == undefined)
        self = {};

    root.find("*[call_js]").each(function(i) {
        var kwargs = $(this).data();
        var funcname = this.getAttribute('call_js');
        var parts = funcname.split('.');
        if (parts.length > 1) {
            import('/static/'+parts[0]+'.js').then((m) => {
                var fn = m[parts[1]];
                if (fn == undefined)
                    console.error("call_js: no such function:", funcname);
                else
                    fn(this, self, kwargs);
               });
        } else {
            var fn = window[funcname];
            if (fn == undefined)
                console.error("call_js: no such function:", funcname);
            else
                fn(this, self, kwargs);
        }
    });
}


