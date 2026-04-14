let experienceStarted = false;
let fireworksStarted = false;
const selectedEffect = new URLSearchParams(window.location.search).get("effect") || "";
let fireworksAudioContext;
let fireworksSoundEnabled = true;
let musicEnabled = true;
let effectsVolume = 0.6;
let experienceProgressTimer = null;

function ensureFireworksAudio() {
    if (!window.AudioContext && !window.webkitAudioContext) {
        return null;
    }

    if (!fireworksAudioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        fireworksAudioContext = new AudioCtx();
    }

    if (fireworksAudioContext.state === "suspended") {
        fireworksAudioContext.resume().catch(() => {});
    }

    return fireworksAudioContext;
}

function playFireworkSound(isEnhanced) {
    if (!fireworksSoundEnabled) {
        return;
    }

    const audioContext = ensureFireworksAudio();
    if (!audioContext) {
        return;
    }

    const now = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    const filter = audioContext.createBiquadFilter();

    oscillator.type = "triangle";
    oscillator.frequency.setValueAtTime(isEnhanced ? 230 : 190, now);
    oscillator.frequency.exponentialRampToValueAtTime(isEnhanced ? 55 : 70, now + 0.45);

    filter.type = "lowpass";
    filter.frequency.setValueAtTime(isEnhanced ? 1500 : 1200, now);

    gainNode.gain.setValueAtTime(0.0001, now);
    gainNode.gain.exponentialRampToValueAtTime((isEnhanced ? 0.07 : 0.045) * effectsVolume, now + 0.02);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.5);

    oscillator.connect(filter);
    filter.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.start(now);
    oscillator.stop(now + 0.52);
}

function startExperience(event) {
    if (experienceStarted) {
        return;
    }
    experienceStarted = true;

    const overlay = document.getElementById("overlay");
    const main = document.getElementById("main-content");
    const music = document.getElementById("music");
    const userName = document.body?.dataset?.userName || "Friend";
    const title = document.getElementById("title");
    const cake = document.getElementById("cake");
    const subWish = document.querySelector(".wish-subtext");
    const darkTransition = document.getElementById("dark-transition");
    const cakeActionText = document.getElementById("cake-action-text");
    const progressFill = document.getElementById("experience-progress");
    const progressTrack = document.querySelector(".experience-progress-track");

    if (!overlay || !main) {
        return;
    }

    const clickX = event?.clientX ?? window.innerWidth / 2;
    const clickY = event?.clientY ?? window.innerHeight / 2;
    ensureFireworksAudio();
    overlay.style.clipPath = `circle(0% at ${clickX}px ${clickY}px)`;

    const introTotalMs = 12400;
    const introStart = Date.now();
    if (experienceProgressTimer) {
        clearInterval(experienceProgressTimer);
    }
    experienceProgressTimer = setInterval(() => {
        const elapsed = Date.now() - introStart;
        const pct = Math.min(100, Math.round((elapsed / introTotalMs) * 100));
        if (progressFill) {
            progressFill.style.width = `${pct}%`;
        }
        if (progressTrack) {
            progressTrack.setAttribute("aria-valuenow", String(pct));
        }
        if (pct >= 100) {
            clearInterval(experienceProgressTimer);
            experienceProgressTimer = null;
        }
    }, 120);

    setTimeout(() => {
        overlay.style.display = "none";
        main.style.display = "block";

        setTimeout(() => {
            title?.classList.add("show");
        }, 600);

        setTimeout(() => {
            cake?.classList.add("show");
            startBalloons();
            if (cakeActionText) {
                cakeActionText.classList.add("show");
            }
        }, 1400);

        setTimeout(() => {
            animateWishFormat(userName);
        }, 2400);

        setTimeout(() => {
            burstConfetti();
        }, 3200);

        setTimeout(() => {
            speakMessage(`Happy Birthday ${userName}. Wishing you a beautiful year ahead.`);
            subWish?.classList.add("show");
        }, 4000);

        if (music) {
            setTimeout(() => {
                music.volume = effectsVolume;
                if (musicEnabled) {
                    music.play().catch(() => {});
                }
            }, 350);
        }

        setTimeout(() => {
            if (!fireworksStarted) {
                if (selectedEffect !== "cake") {
                    const enhanced = selectedEffect === "fireworks";
                    startDarkToFireworksTransition(enhanced);
                }
            }
        }, 9800);
    }, 2600);
}

function startDarkToFireworksTransition(isEnhanced) {
    const darkTransition = document.getElementById("dark-transition");
    if (darkTransition) {
        darkTransition.classList.add("active");
    }

    setTimeout(() => {
        showFireworksPhase(isEnhanced);
        const progressFill = document.getElementById("experience-progress");
        const progressTrack = document.querySelector(".experience-progress-track");
        if (experienceProgressTimer) {
            clearInterval(experienceProgressTimer);
            experienceProgressTimer = null;
        }
        if (progressFill) {
            progressFill.style.width = "100%";
        }
        if (progressTrack) {
            progressTrack.setAttribute("aria-valuenow", "100");
        }
        if (darkTransition) {
            darkTransition.classList.remove("active");
        }
    }, 1100);
}

function speakMessage(text) {
    if (!("speechSynthesis" in window)) {
        return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    speechSynthesis.speak(utterance);
}

function startBalloons() {
    const container = document.getElementById("balloons");
    if (!container) {
        return;
    }

    container.innerHTML = "";
    const colors = ["#ff4d6d", "#4cc9f0", "#f9c74f", "#80ed99", "#c77dff"];

    const spawnBalloon = () => {
        const balloon = document.createElement("div");
        balloon.className = "balloon";
        balloon.style.background = colors[Math.floor(Math.random() * colors.length)];
        balloon.style.left = `${Math.random() * 100}%`;
        balloon.style.animationDuration = `${6 + Math.random() * 5}s`;
        balloon.style.opacity = `${0.7 + Math.random() * 0.3}`;
        balloon.style.width = `${36 + Math.random() * 24}px`;
        balloon.style.height = `${54 + Math.random() * 36}px`;
        balloon.style.setProperty("--drift", `${Math.random() * 80 - 40}px`);
        container.appendChild(balloon);

        setTimeout(() => {
            balloon.remove();
        }, 12500);
    };

    for (let index = 0; index < 18; index += 1) {
        setTimeout(spawnBalloon, index * 120);
    }

    const stream = setInterval(spawnBalloon, 520);
    setTimeout(() => {
        clearInterval(stream);
    }, 11000);
}

function burstConfetti() {
    if (typeof confetti !== "function") {
        return;
    }

    const duration = 2200;
    const end = Date.now() + duration;

    (function frame() {
        confetti({
            particleCount: 6,
            spread: 70,
            startVelocity: 30,
            origin: { x: Math.random(), y: Math.random() * 0.45 },
        });
        if (Date.now() < end) {
            requestAnimationFrame(frame);
        }
    })();
}

function showFireworksPhase(isEnhanced = false) {
    if (fireworksStarted) {
        return;
    }
    fireworksStarted = true;

    const cakeScreen = document.getElementById("cake-screen");
    const fireworksScreen = document.getElementById("fireworks-screen");
    if (!cakeScreen || !fireworksScreen) {
        return;
    }

    cakeScreen.classList.remove("active");
    fireworksScreen.classList.add("active");
    fireworksScreen.classList.toggle("enhanced", isEnhanced);
    const wishTitle = fireworksScreen.querySelector(".wish-text");
    wishTitle?.classList.add("show");
    runFireworks(isEnhanced);

    setTimeout(() => {
        const notePanel = document.getElementById("final-note-panel");
        notePanel?.classList.add("show");
    }, isEnhanced ? 5200 : 6800);

    setTimeout(() => {
        document.getElementById("slideshow-panel")?.classList.add("show");
    }, isEnhanced ? 2600 : 3200);

    setTimeout(() => {
        document.getElementById("messages-panel")?.classList.add("show");
    }, isEnhanced ? 3500 : 4400);

    setTimeout(() => {
        document.getElementById("gifts-panel")?.classList.add("show");
    }, isEnhanced ? 4300 : 5400);
}

function runFireworks(isEnhanced = false) {
    const canvas = document.getElementById("fireworks-canvas");
    if (!canvas) {
        return;
    }

    const context = canvas.getContext("2d");
    const particles = [];
    const resizeCanvas = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    function createExplosion(x, y) {
        const burstCount = isEnhanced ? 85 : 60;
        for (let index = 0; index < burstCount; index += 1) {
            const angle = (Math.PI * 2 * index) / burstCount;
            const speed = Math.random() * (isEnhanced ? 4.6 : 3.5) + 1.3;
            particles.push({
                x,
                y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                life: isEnhanced ? 130 : 100,
                color: `hsl(${Math.random() * 360}, 90%, 65%)`,
            });
        }
    }

    let frames = 0;
    function animate() {
        frames += 1;
        context.fillStyle = "rgba(8, 8, 18, 0.24)";
        context.fillRect(0, 0, canvas.width, canvas.height);

        if (frames % (isEnhanced ? 20 : 30) === 0) {
            createExplosion(
                Math.random() * canvas.width,
                Math.random() * (canvas.height * 0.6) + 40,
            );
            playFireworkSound(isEnhanced);
            if (typeof confetti === "function") {
                confetti({
                    particleCount: isEnhanced ? 55 : 30,
                    spread: isEnhanced ? 78 : 55,
                    origin: {
                        x: Math.random(),
                        y: Math.random() * 0.5,
                    },
                });
            }
        }

        for (let index = particles.length - 1; index >= 0; index -= 1) {
            const particle = particles[index];
            particle.x += particle.vx;
            particle.y += particle.vy;
            particle.vy += 0.02;
            particle.life -= 1;

            if (particle.life <= 0) {
                particles.splice(index, 1);
                continue;
            }

            context.fillStyle = particle.color;
            context.globalAlpha = particle.life / 100;
            context.beginPath();
            context.arc(particle.x, particle.y, 2.2, 0, Math.PI * 2);
            context.fill();
            context.globalAlpha = 1;
        }

        if (frames < 900) {
            requestAnimationFrame(animate);
        }
    }

    animate();
}

function animateWishFormat(userName) {
    const wishCard = document.getElementById("wish-card");
    const typingTarget = document.getElementById("wish-typing");
    const cake = document.getElementById("cake");

    if (wishCard) {
        wishCard.classList.add("show");
    }

    if (cake) {
        cake.classList.add("celebrate");
        setTimeout(() => {
            cake.classList.remove("celebrate");
        }, 2600);
    }

    if (!typingTarget) {
        return;
    }

    const message = `Happy Birthday, ${userName}! Today is all about your smile and your dreams.`;
    let index = 0;
    typingTarget.textContent = "";

    const timer = setInterval(() => {
        typingTarget.textContent += message[index];
        index += 1;

        if (index >= message.length) {
            clearInterval(timer);
        }
    }, 32);
}

const overlayElement = document.getElementById("overlay");
if (overlayElement) {
    overlayElement.addEventListener("click", startExperience);
    overlayElement.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            startExperience(event);
        }
    });
}

function enableCakeInteraction() {
    const cake = document.getElementById("cake");
    const cakeActionText = document.getElementById("cake-action-text");
    if (!cake) {
        return;
    }

    cake.addEventListener("click", () => {
        if (cake.classList.contains("blown")) {
            return;
        }

        cake.classList.add("blown");
        if (cakeActionText) {
            cakeActionText.textContent = "Candles blown! Make a wish 🌟";
        }

        if (typeof confetti === "function") {
            confetti({
                particleCount: 45,
                spread: 60,
                origin: { x: 0.5, y: 0.62 },
            });
        }

        setTimeout(() => {
            if (cakeActionText) {
                cakeActionText.textContent = "Cake cut complete! Get ready for the finale...";
            }
            startDarkToFireworksTransition(true);
        }, 1000);
    });

    if (selectedEffect === "cake" && cakeActionText) {
        cakeActionText.classList.add("show");
        cakeActionText.textContent = "Cake view mode: click to cut and start dark fireworks finale ✨";
    }
}

enableCakeInteraction();

function setupSlideshow() {
    const imageElement = document.getElementById("slideshow-image");
    if (!imageElement) {
        return;
    }

    let imageList = [];
    try {
        imageList = JSON.parse(imageElement.dataset.images || "[]");
    } catch {
        imageList = [];
    }

    if (!Array.isArray(imageList) || imageList.length <= 1) {
        return;
    }

    let activeIndex = 0;
    setInterval(() => {
        activeIndex = (activeIndex + 1) % imageList.length;
        imageElement.src = imageList[activeIndex];
    }, 2400);
}

setupSlideshow();

function setupExperienceControls() {
    const skipButton = document.getElementById("skip-experience");
    const replayButton = document.getElementById("replay-experience");
    const overlay = document.getElementById("overlay");
    const main = document.getElementById("main-content");

    if (skipButton) {
        skipButton.addEventListener("click", () => {
            if (overlay) {
                overlay.style.display = "none";
            }
            if (main) {
                main.style.display = "block";
            }
            if (!fireworksStarted) {
                startDarkToFireworksTransition(true);
            }
        });
    }

    if (replayButton) {
        replayButton.addEventListener("click", () => {
            window.location.reload();
        });
    }
}

setupExperienceControls();