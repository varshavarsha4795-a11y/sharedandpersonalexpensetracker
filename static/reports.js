window.onload = function () {

    // ================= GENERATE REPORT (Month Filter) =================

    const generateBtn = document.getElementById("generateBtn");
    const monthFilter = document.getElementById("monthFilter");
    const downloadLink = document.getElementById("downloadReportLink");

    if (generateBtn && monthFilter) {

        generateBtn.addEventListener("click", function () {

            const month = monthFilter.value;

            if (month) {
                window.location.href = "/reports?month=" + month;
            } else {
                window.location.href = "/reports";
            }

        });

        // Keep the Download Report button in sync as the user picks a month,
        // even before they click Generate.
        if (downloadLink) {
            monthFilter.addEventListener("change", function () {
                const month = monthFilter.value;
                downloadLink.href = month
                    ? "/download_report?month=" + month
                    : "/download_report";
            });
        }
    }

    // ================= BAR CHART =================

    const barCtx = document.getElementById("barChart").getContext("2d");

    new Chart(barCtx, {
        type: "bar",

        data: {
            labels: chartLabels,
            datasets: [{
                label: "Expense (₹)",
                data: chartData,
                backgroundColor: [
                    "#8A2BE2",
                    "#FF5C8A",
                    "#3FA9F5",
                    "#FFC857",
                    "#4BC0C0"
                ],

                borderRadius: 8,
                borderSkipped: false,
                barThickness: 35
            }]
        },

        options: {

            responsive: true,
            maintainAspectRatio: false,

            plugins: {
                legend: {
                    display: false
                }
            },

            scales: {

                x: {
                    ticks: {
                        color: "#ffffff",
                        font: {
                            size: 12
                        }
                    },

                    grid: {
                        display: false
                    }

                },

                y: {

                    beginAtZero: true,

                    ticks: {
                        color: "#ffffff"
                    },

                    grid: {
                        color: "rgba(255,255,255,0.08)"
                    }

                }

            }

        }

    });

    // ================= PIE CHART =================

    const pieCtx = document.getElementById("pieChart").getContext("2d");

    new Chart(pieCtx, {

        type: "pie",

        data: {

            labels: chartLabels,
            datasets: [{

                data: chartData,

                backgroundColor: [
                    "#8A2BE2",
                    "#FF5C8A",
                    "#3FA9F5",
                    "#FFC857",
                    "#4BC0C0"
                ],

                borderWidth: 2,
                borderColor: "#2b1147"

            }]

        },

        options: {

            responsive: true,
            maintainAspectRatio: false,

            plugins: {

                legend: {

                    position: "bottom",

                    labels: {

                        color: "#ffffff",
                        padding: 15,
                        font: {
                            size: 12
                        }

                    }

                }

            }

        }

    });

};