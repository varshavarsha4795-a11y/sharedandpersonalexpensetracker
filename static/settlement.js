// Settlement Page JavaScript

document.addEventListener("DOMContentLoaded", function () {

    const payBtn = document.getElementById("payBtn");

    // Guard: this page now marks payments paid via the
    // "Mark Paid" links generated per settlement row, so this
    // optional legacy button only runs if it actually exists.
    if (!payBtn) {
        return;
    }

    const member = document.querySelector("select");
    const amount = document.querySelector("input");
    const history = document.querySelector("ul");

    payBtn.addEventListener("click", function () {

        if (!member || !amount || member.value === "" || amount.value === "") {
            alert("Please select a member and enter the amount.");
            return;
        }

        alert(member.value + " has successfully paid ₹" + amount.value + " 🎉");

        if (history) {
            const li = document.createElement("li");
            li.innerHTML = "✅ " + member.value + " paid ₹" + amount.value;
            history.prepend(li);
        }

        amount.value = "";

    });

});