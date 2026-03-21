document.querySelectorAll("form").forEach((formElement) => {
    formElement.addEventListener("submit", () => {
        const submitButton = formElement.querySelector("button[type='submit']");
        if (!submitButton) {
            return;
        }

        submitButton.disabled = true;
        submitButton.dataset.originalLabel = submitButton.textContent;
        submitButton.textContent = "Please wait...";
        submitButton.classList.add("is-loading");
    });
});
