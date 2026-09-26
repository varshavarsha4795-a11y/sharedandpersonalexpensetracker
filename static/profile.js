document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('photoInput');
    var form = document.getElementById('photoForm');

    if (input && form) {
        input.addEventListener('change', function () {
            if (input.files && input.files.length > 0) {
                form.submit();
            }
        });
    }
});
