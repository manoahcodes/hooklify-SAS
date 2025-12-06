function startStatusPoll(statusUrl, overlayId = "pending-overlay", redirectUrl) {
    // Use a counter to limit retries on severe errors
    var errorCount = 0; 
    var maxErrors = 5; // Stop after 5 consecutive errors

    function poll() {
        $.ajax({
            url: statusUrl,
            method: "GET",
            dataType: "json",
            success: function (data) {
                errorCount = 0; // Reset error count on success
                
                if (data.activated) {
                    // Optional — fade out visual
                    $("#" + overlayId).fadeOut(200);
                    window.location.href = redirectUrl;

                } else {
                    // Subscription not ready, wait and try again
                    setTimeout(poll, 3000);
                }
            },
            error: function (xhr, status, error) {
                errorCount++;
                console.error("Polling error (" + xhr.status + "):", error);
                
                if (errorCount >= maxErrors) {
                    // If we hit max errors, stop polling and redirect to a safe page (e.g., dashboard/plans)
                    console.error("Max polling errors reached. Redirecting to dashboard.");
                    alert("We encountered a persistent error verifying your payment. Contact support or visit your dashboard.");
                    window.location.href = redirectUrl; 
                } else {
                    // Retry with a slightly longer delay after an error
                    setTimeout(poll, 5000);
                }
            }
        });
    }

    poll();
}


function startCountdown(seconds, timerId, redirectUrl) {
    let countdown = seconds;
    const timerEl = document.getElementById(timerId);

    if (!timerEl) {
        console.error("Countdown element not found:", timerId);
        return;
    }

    // initialize timer display
    timerEl.textContent = countdown;

    const interval = setInterval(() => {
        countdown--;
        timerEl.textContent = countdown;

        if (countdown <= 0) {
            clearInterval(interval);
            // redirect to dashboard
            window.location.href = redirectUrl;
        }
    }, 1000);
}