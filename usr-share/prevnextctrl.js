

import {get_tester} from "./autotest.js"
let test = get_tester('prevnextctrl');

/* create a HTML control with ids for start, left, right, end buttons and two locations to
 * show the offset and the total, then call this function (once!) using call_js
 */

export function setup_control({start_id, left_id, right_id, end_id, offset_id, total_id, count}, callback) {

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

    function set_button_status(o, m) {
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


export function on_click_do(element_id, fn) {
    $('#' + element_id).unbind('click').click(e => {
        e.preventDefault();
        fn();
    });
}


test(function set_on_click() {
    let element = $('<div>', {id: 'element_id'});
    $('html').append(element);
    let clicks = [];
    on_click_do("element_id", () => clicks.push(1));
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

