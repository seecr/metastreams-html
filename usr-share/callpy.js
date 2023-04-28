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


function parse_value(v) {
    validate("N|S", [v]);
    let p = parseFloat(v);
    if (isNaN(p))
        return v;
    return p
}


function headers2map(headers) {
    validate("S", [headers]);
    // I did not find a Headers parser. This one support only one value per key,
    // but that is enough for Python arguments.
    return Object.fromEntries(
        headers
        .split("\r\n")
        .map(line => line.split(": "))
        .filter(([key, value]) => key.startsWith('py-arg-'))
        .map(([key, value]) => [key.substring(7,99), parse_value(value)]));
}


test(function headers2map_test() {
    // TODO
})


//
// Call a Python function in a .sf, marked with callpy.jscallable.
//
export function call_py(funcname, kwargs = {}, done) {
    validate("SOF", arguments);
    let query = {call_py: funcname, data: JSON.stringify(kwargs)};
    let url = new URL(location);
    const response = $.get(url.origin + url.pathname, query);
    response
        .done(data => done(data, headers2map(response.getAllResponseHeaders())))
        .fail(m => console.error("CallJs ERROR calling", funcname, '(', kwargs, '):', m));
}
/*

test(function call_py_basics() {
    call_py('call_py_basics', {n: 17, name: "Mies"}, (body, kwargs) => {
        test.eq("Hello Mies!", body);
        test.eq(34, kwargs.result);
    });
})


test(function call_py_returns_types() {
    call_py('call_py_returns_types', {i: 13, f: 3.14, s: "Aap"}, (body, kwargs) => {
        test.eq(13, kwargs.i);
        test.eq(3.14, kwargs.f);
        test.eq("Aap", kwargs.s);
        test.eq("13, 3.14, 'Aap'", body);
    });
})
*/



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


