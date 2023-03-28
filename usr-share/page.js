

// see corresponding modal stuff in page.sf
export function show_modal(data, modal_id) {
    const _modal = $('#' + modal_id);
    _modal.find(".modal-body")
        .empty()
        .append(data)
        .find('textarea')
        .height(window.innerHeight/1.5);
    _modal.modal('show');
}

