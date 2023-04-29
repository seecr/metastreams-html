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

/*
 * autotest like tester
 * sadly, most browser still do not support @decorator syntax
 */


export function get_tester(name) {
    let test = function(test_fn) {
        console.log('TEST:'+name+':'+test_fn.name);
        let html = $('html');
        /*
         * we make room for the test to manipulate the dom, and it is important
         * to do that in such a way that jQuery data is also saved.
         * detach() does that.
         */
        let save = html.children().detach();
        try {
            test_fn();
        } finally {
            html.empty();        // remove test's crap
            save.appendTo(html); // restore dom
        }
    };

    test.eq = function eq(lhs, rhs) {
        if (JSON.stringify(lhs) != JSON.stringify(rhs)) {
            console.error("eq", lhs, rhs);
            debugger;
        };
    };
    return test;
}
