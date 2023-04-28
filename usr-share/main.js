

import {call_js_all} from "./callpy.js"


$(document).ready(function () {
    // show a wait mouse cursor during load
    $(document).ajaxStart(function () { $("html").addClass("wait"); });

    // execute all Python initialted call_js functions
    call_js_all();

    // stop the wait mouse cursor
    $(document).ajaxStop(function () { $("html").removeClass("wait"); });
});


