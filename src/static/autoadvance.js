/**
 * Automatically advance the cursor to the next form field if you've entered
 * one character in the current text box.
 *
 * @param event An input event
 */
function auto_advance(event) {
    if (event.target.value.length === 1) {
        if (!findForm(event.target).tabOrder) {
            update_tab_hack_array(event.target);
        }
        // find the next element in the tabbing order and focus it
        // if the last element of the form then blur
        // (this can be changed to focus the next <form> if any)
        for (var j = 0, jl = findForm(event.target).tabOrder.length; j < jl; j++) {
            if (event.target === findForm(event.target).tabOrder[j]) {
                if (j + 1 < jl) {
                    findForm(event.target).tabOrder[j + 1].focus();
                } else {
                    event.target.blur();
                }
            }
        }
    }
}

/**
 * Locate the nearest parent <form>.
 *
 * @param elem The element for which to find the parent form
 * @returns {*} The nearest parent form of <code>elem</code>
 */
function findForm(elem) {
    var nextElem = elem;
    while (nextElem.tagName !== "BODY" && nextElem.tagName !== "FORM") {
        nextElem = nextElem.parentNode;
    }
    return nextElem;
}

// c/o StackOverflow: https://stackoverflow.com/a/7329696
/** * Update an array stored in a form, which keeps track of what order the
 * elements are in, for auto-tabbing.
 *
 * @param elem The element to begin looking for the form at
 */
function update_tab_hack_array(elem) {
    var els = findForm(elem).elements,
        ti = [],
        rest = [];

    // store all focusable form elements with tabIndex > 0
    for (var i = 0, il = els.length; i < il; i++) {
        if (els[i].tabIndex > 0 &&
            !els[i].disabled &&
            !els[i].hidden &&
            !els[i].readOnly &&
            els[i].type !== 'hidden') {
            ti.push(els[i]);
        }
    }

    // sort them by tabIndex order
    ti.sort(function (a, b) {
        return a.tabIndex - b.tabIndex;
    });

    // store the rest of the elements in order
    for (i = 0, il = els.length; i < il; i++) {
        if (els[i].tabIndex == 0 &&
            !els[i].disabled &&
            !els[i].hidden &&
            !els[i].readOnly &&
            els[i].type !== 'hidden') {
            rest.push(els[i]);
        }
    }

    // store the full tabbing order
    findForm(elem).tabOrder = ti.concat(rest);
}

// Find the room inputs and convert them to an Array, so I can .forEach them
rooms = Array.prototype.slice.call(
    document.getElementsByClassName('room-input'), 0);
// Bind the auto_advance function to every room except 1650, since that
// might have numbers of people that require two digits to represent.
rooms.forEach(function bind(e) {
    if (e.name !== "1650") {
        e.addEventListener('input', auto_advance);
    }
});
// Initially update the tab hack array.
update_tab_hack_array(document.getElementById('reverse-inputs'));
document.getElementById("reverse-inputs").addEventListener('click', function (ev) {
    update_tab_hack_array(ev.target);
}); 