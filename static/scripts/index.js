function filterOrders() {
    const input = document.getElementById("orderSearch").value.toLowerCase();
    const orderItems = document.querySelectorAll(".order-item");

    orderItems.forEach((item) => {
        const cardText = item.innerText.toLowerCase();
        if (cardText.includes(input)) {
            item.style.display = "";  // Show the card
        } else {
            item.style.display = "none";  // Hide the card
        }
    });
}
document.addEventListener("DOMContentLoaded", function () {
    const circle = document.querySelector(".checkmark-circle");
    const check = document.querySelector(".checkmark-check");

    // Optional: Log animations if debugging
    circle.addEventListener("animationend", () => console.log("Circle animation complete"));
    check.addEventListener("animationend", () => console.log("Check animation complete"));
});
