function toggle_tab_order() {
    var checkbox = document.getElementById("reverse-inputs");
    var roomInputs = Array.prototype.slice.call(
        document.getElementsByClassName('room-input'), 0);
    roomInputs.splice(0, 0, document.getElementById('time'));
    roomInputs.splice(0, 0, document.getElementById('date'));
    var numRooms = roomInputs.length;

    if (checkbox.checked) {
        for (var i = 0; i < numRooms; i++) {
            roomInputs[i].tabIndex = (numRooms - i) + 1;
        }
    } else {
        // BUG: In Firefox, this doesn't let the user tab back to the time
        // fields again.  Will fix later, since it's a bit of an edge case.
        roomInputs.forEach(function (room) {
            room.removeAttribute("tabIndex");
        });
    }
}

document.getElementById("reverse-inputs").addEventListener(
    'click', toggle_tab_order);