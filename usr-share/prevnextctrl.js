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


import {call_py, replace_content} from "./callpy.js"
import {get_tester} from "./autotest.js"
import {validate} from "./aproba.js";

let test = get_tester('prevnextctrl');


/* create a HTML control with ids for start, left, right, end buttons and two locations to
 * show the offset and the total, then call this function (once!) using call_js
 * then call set_button_status(offset, maxitems) as to update the control
 */

export function setup_control({start_id, left_id, right_id, end_id, offset_id, total_id, count}, callback) {
    validate("SSSSSSNF", [start_id, left_id, right_id, end_id, offset_id, total_id, count, callback]);

    let offset = 0;
    let maxitems = 9999;
    let estart  = $('#' + start_id);
    let eleft   = $('#' + left_id);
    let eright  = $('#' + right_id);
    let eend    = $('#' + end_id);
    let eoffset = $('#' + offset_id);
    let etotal  = $('#' + total_id);
    console.assert(estart.prop('tagName') == 'BUTTON');
    console.assert(eleft.prop('tagName') == 'BUTTON');
    console.assert(eright.prop('tagName') == 'BUTTON');
    console.assert(eend.prop('tagName') == 'BUTTON');
    console.assert(count > 0);

    function set_button_status(o, m) {
        validate("NN", arguments);
        offset = Math.max(o, 0);
        maxitems = m;
        estart .prop('disabled', offset <= 0);
        eleft  .prop('disabled', offset <= 0);
        eright .prop('disabled', offset + count >= maxitems);
        eend   .prop('disabled', offset + count >= maxitems);
        eoffset.text(offset);
        etotal .text(maxitems);
    }

    function _on_click_do(id, update_offset) {
        validate("SF", arguments);
        on_click_do(id, () => {
            update_offset();
            set_button_status(offset, maxitems);
            callback(offset, count);
        });
    }

    _on_click_do(start_id, () => offset = 0);
    _on_click_do( left_id, () => offset -= count);
    _on_click_do(right_id, () => offset += count);
    _on_click_do(  end_id, () => offset = maxitems - count);

    set_button_status(offset, maxitems);
    return set_button_status;
}


export function generic_init(_, self, {
            count, offset_id, start_id, left_id, right_id, end_id, total_id,
            results_ph, py_fn_name, ...py_fn_piggies}) {
    validate("NSSSSSSSSO", [
        count, offset_id, start_id, left_id, right_id, end_id, total_id,
        results_ph, py_fn_name, py_fn_piggies]);
    let results_elm = $('#' + results_ph);
    function get_data_and_update(offset) {
        call_py(py_fn_name, {offset, count, ...py_fn_piggies},
            (data, {maxitems}) => {
                replace_content(results_elm, data);
                update_buttons(offset, maxitems);
            });
    }
    let update_buttons = setup_control(
        {count, offset_id, start_id, left_id, right_id, end_id, total_id}, get_data_and_update);
    get_data_and_update(0);
}


export function on_click_do(element, fn) {
    validate("OF|SF", arguments);
    if (element instanceof Element)
        element = $(element);
    else
        element = $('#' + element);
    element.unbind('click').click(e => {
        e.preventDefault();
        fn();
    });
}


test(function set_on_click_with_id() {
    let element = $('<div>', {id: 'element_id'});
    $('html').append(element);
    let clicks = [];
    on_click_do("element_id", () => clicks.push(1));
    element.click();
    test.eq(1, clicks[0]);
});


test(function set_on_click_element() {
    let element = document.createElement('div');
    let clicks = [];
    on_click_do(element, () => clicks.push(1));
    element.click();
    test.eq(1, clicks[0]);
});



test(function create_control() {
    let start  = $('<button>', {id: 's_id'});
    let left   = $('<button>', {id: 'l_id'});
    let right  = $('<button>', {id: 'r_id'});
    let end    = $('<button>', {id: 'e_id'});
    let offset = $('<button>', {id: 'o_id'});
    let total  = $('<button>', {id: 't_id'});
    $('html').append(start, left, right, end, offset, total);

    let results = [];
    let set_status = setup_control(
        {start_id: 's_id', left_id: 'l_id', right_id: 'r_id',
         end_id: 'e_id', offset_id: 'o_id', total_id: 't_id', count: 2},
        (offset, count) => results.push([offset, count]));

    function check_disabled(l, s, r, e) {
        test.eq(l,  left.prop('disabled'));
        test.eq(s, start.prop('disabled'));
        test.eq(r, right.prop('disabled'));
        test.eq(e,   end.prop('disabled'));
    };

    set_status(3, 7);
    test.eq('3', offset.text());
    test.eq('7', total.text());
    check_disabled(false, false, false, false);
    left.click();
    test.eq([1, 2], results[0]);
    left.click();
    test.eq([0, 2], results[1]);
    test.eq('0', offset.text());
    check_disabled(true, true, false, false);

    right.click();
    test.eq('2', offset.text());
    check_disabled(false, false, false, false);
    test.eq([2, 2], results[2]);
    right.click();
    test.eq('4', offset.text());
    test.eq([4, 2], results[3]);
    right.click();
    test.eq('6', offset.text());
    test.eq([6, 2], results[4]);
    check_disabled(false, false, true, true);

    start.click();
    test.eq('0', offset.text());
    test.eq([0, 2], results[5]);
    check_disabled(true, true, false, false);

    end.click();
    test.eq('5', offset.text());
    test.eq([5, 2], results[6]);
    check_disabled(false, false, true, true);

    set_status(-3, 9);
    test.eq('0', offset.text());
    test.eq('9', total.text());
    check_disabled(true, true, false, false);
});


test(function accept_only_buttons() {
    let start  = $('<button>', {id: 's_id'});
    let left   = $('<button>', {id: 'l_id'});
    let right  = $('<button>', {id: 'r_id'});
    let end    = $('<button>', {id: 'e_id'});
    let offset = $('<button>', {id: 'o_id'});
    let total  = $('<button>', {id: 't_id'});
    $('html').append(start, left, right, end, offset, total);

    let set_status = setup_control(
        {start_id: 's_id', left_id: 'l_id', right_id: 'r_id',
         end_id: 'e_id', offset_id: 'o_id', total_id: 't_id', count: 2},
        (offset, count) => []);
});

