document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("#opdvisit_form") || document.querySelector("#content-main form");
    const doctorField = document.getElementById("id_doctor");
    const feeField = document.getElementById("id_fee");
    const totalField = document.getElementById("id_total");
    const isAddPage = window.location.pathname.endsWith("/add/");

    if (form && isAddPage) {
        function ensureAddAnotherMarker() {
            let marker = form.querySelector("input[data-enter-addanother='true']");

            if (!marker) {
                marker = document.createElement("input");
                marker.type = "hidden";
                marker.name = "_addanother";
                marker.value = "1";
                marker.setAttribute("data-enter-addanother", "true");
                form.appendChild(marker);
            }

            return marker;
        }

        function submitAsAddAnother() {
            ensureAddAnotherMarker();

            const saveAddAnotherButton = form.querySelector("input[name='_addanother'], button[name='_addanother']");
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit(saveAddAnotherButton || undefined);
                return;
            }

            if (saveAddAnotherButton) {
                saveAddAnotherButton.click();
                return;
            }

            form.submit();
        }

        form.addEventListener("keydown", function (event) {
            if (event.key !== "Enter") {
                return;
            }

            if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || event.isComposing) {
                return;
            }

            const target = event.target;
            if (target && target.tagName === "TEXTAREA") {
                return;
            }

            const targetType = target && target.type ? target.type.toLowerCase() : "";
            if (targetType === "submit" || targetType === "button") {
                return;
            }

            event.preventDefault();
            submitAsAddAnother();
        });

        form.addEventListener("submit", function (event) {
            const submitterName = event.submitter && event.submitter.name ? event.submitter.name : "";
            const validSubmitters = ["_addanother", "_save", "_continue"];
            if (!validSubmitters.includes(submitterName)) {
                ensureAddAnotherMarker();
            }
        });
    }

    if (!doctorField || !feeField || !totalField) {
        return;
    }

    let doctorFees = {};
    try {
        doctorFees = JSON.parse(doctorField.dataset.doctorFees || "{}");
    } catch (error) {
        doctorFees = {};
    }

    function syncDoctorFee() {
        const selectedDoctorId = doctorField.value;
        const doctorFee = parseFloat(doctorFees[selectedDoctorId]);

        if (!Number.isNaN(doctorFee)) {
            const normalizedFee = doctorFee.toFixed(2);
            feeField.value = normalizedFee;
            totalField.value = normalizedFee;
        }
    }

    doctorField.addEventListener("change", syncDoctorFee);
    syncDoctorFee();
});
