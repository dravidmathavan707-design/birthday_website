const wheelElement = document.getElementById("lucky-wheel");
const spinButton = document.getElementById("spin-wheel");
const wheelResult = document.getElementById("wheel-result");

const wheelPrizes = [
    "Big Smile 😄",
    "Dream Day ✨",
    "Chocolate Treat 🍫",
    "Lucky Star ⭐",
    "Gift Time 🎁",
    "Fun Bonus 🎉",
];

let wheelRotation = 0;
let wheelLocked = false;

if (spinButton && wheelElement && wheelResult) {
    spinButton.addEventListener("click", () => {
        if (wheelLocked) {
            return;
        }

        wheelLocked = true;
        const randomIndex = Math.floor(Math.random() * wheelPrizes.length);
        const segmentAngle = 360 / wheelPrizes.length;
        const targetAngle = 360 * 5 + (360 - (randomIndex * segmentAngle + segmentAngle / 2));

        wheelRotation = targetAngle;
        wheelElement.style.transform = `rotate(${wheelRotation}deg)`;

        setTimeout(() => {
            wheelResult.textContent = `You got: ${wheelPrizes[randomIndex]}`;
            wheelLocked = false;
        }, 4200);
    });
}

const guessInput = document.getElementById("guess-input");
const guessButton = document.getElementById("guess-btn");
const guessResult = document.getElementById("guess-result");

if (guessButton && guessInput && guessResult) {
    guessButton.addEventListener("click", () => {
        const guess = Number(guessInput.value);
        const luckyNumber = Math.floor(Math.random() * 10) + 1;

        if (!guess || guess < 1 || guess > 10) {
            guessResult.textContent = "Enter a number between 1 and 10.";
            return;
        }

        if (guess === luckyNumber) {
            guessResult.textContent = "Amazing! You guessed correctly 🎯";
        } else {
            guessResult.textContent = `Not this time. Lucky number was ${luckyNumber}. Try again!`;
        }
    });
}

const rpsButtons = document.querySelectorAll(".rps-btn");
const rpsResult = document.getElementById("rps-result");
const rpsChoices = ["rock", "paper", "scissors"];

if (rpsButtons.length && rpsResult) {
    rpsButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const userChoice = button.dataset.choice;
            const cpuChoice = rpsChoices[Math.floor(Math.random() * rpsChoices.length)];

            if (userChoice === cpuChoice) {
                rpsResult.textContent = `Draw! You both picked ${cpuChoice}.`;
                return;
            }

            const win =
                (userChoice === "rock" && cpuChoice === "scissors") ||
                (userChoice === "paper" && cpuChoice === "rock") ||
                (userChoice === "scissors" && cpuChoice === "paper");

            rpsResult.textContent = win
                ? `You win! ${userChoice} beats ${cpuChoice} 🎉`
                : `You lose! ${cpuChoice} beats ${userChoice}.`;
        });
    });
}
