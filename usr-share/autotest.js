
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
