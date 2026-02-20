document.addEventListener("DOMContentLoaded", function () {

    let input = document.getElementById("stockInput");
    let box = document.getElementById("suggestionBox");

    input.addEventListener("keyup", function () {

        let value = input.value;

        if (value.length < 1) {
            box.style.display = "none";
            return;
        }

        fetch("/search_stock?q=" + value)
            .then(response => response.json())
            .then(data => {

                box.innerHTML = "";

                if (data.length === 0) {
                    box.style.display = "none";
                    return;
                }

                box.style.display = "block";

                data.forEach(function (item) {

                    let div = document.createElement("div");
                    div.innerHTML = item;

                    div.onclick = function () {
                        input.value = item;
                        box.style.display = "none";
                    };

                    box.appendChild(div);

                });

            });
    });
});