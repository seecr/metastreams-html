
/*
 * autotest like tester
 * sadly, most browser still do not support @decorator syntax
 */


export function get_tester(name) {
    let test = function(test_fn) {
        console.log('TEST:'+name+':'+test_fn.name);
        test_fn();
    };

    test.eq = function eq(lhs, rhs) {
        if (JSON.stringify(lhs) != JSON.stringify(rhs)) {
            console.error("eq", lhs, rhs);
            debugger;
        };
    };
    return test;
}
