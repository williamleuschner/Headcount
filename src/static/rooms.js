var roomInputs = null;
var currentHighlight = null;

function highlightRoom(e) {
    currentHighlight.style.stroke = "";
    e = e || window.event;
    var target = e.target || e.srcElement;
    console.log(target);
    currentHighlight = document.getElementsByClassName(target.name)[0];
    currentHighlight.style.stroke = "#FF0000";

}

function addListener(element, type, callback) {
    if (element.addEventListener) {
        element.addEventListener(type, callback, false);
    } else {
        element.attachEvent("on" + type, callback);
    }
}

function main() {
    roomInputs = document.getElementsByClassName("room-input");
    currentHighlight = {"style": {"stroke": ""}};
    for (var i = 0; i < roomInputs.length; i++) {
        addListener(roomInputs[i], "focus", function (e) {
            highlightRoom(e)
        });
    }
}

main();
