function auto_advance() {

}

rooms = document.getElementsByClassName('room-input');
rooms.forEach(function bind(e) {
    if (e.name !== "1650") {
        e.oninput = auto_advance;
    }
});