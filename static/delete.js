
const deleteModalEl = document.getElementById('deleteModal');
deleteModalEl.addEventListener('show.bs.modal', function (event) {
    let url = event.relatedTarget.dataset.url;
    let form = this.querySelector('form');
    form.action = url; 
    let span = this.querySelector('.delete-title');
    span.textContent = event.relatedTarget.dataset.title;
});