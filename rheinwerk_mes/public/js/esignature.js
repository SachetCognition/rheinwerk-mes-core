// Signing dialog for the four dispositive acts (DEC-W2-029, enforced in W3).
//
// German-first, one screen, no dead air: the act being signed and its meaning are shown as
// read-only text so the signer sees *what* they declare, the password is never kept, and the
// confirm button reports progress on itself while the server re-authenticates.

frappe.provide("rheinwerk_mes.esignature");

rheinwerk_mes.esignature = {
	ACTS: {
		"qa_state:Released": { label: __("Chargenfreigabe"), meaning: __("Freigegeben"), reason: true },
		"qa_state:Blocked": { label: __("Chargensperre"), meaning: __("Gesperrt"), reason: true },
		"coa:issue": { label: __("Ausstellung eines Analysenzertifikats"), meaning: __("Zertifiziert"), reason: false },
		"gov_state:Accepted": { label: __("Rezeptfreigabe"), meaning: __("Rezeptur genehmigt"), reason: false },
	},

	// Opens the dialog and resolves with the signature name once the server accepted it.
	sign(document_type, document_name, act, transition) {
		const spec = this.ACTS[act];
		return new Promise((resolve, reject) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Elektronische Unterschrift"),
				fields: [
					{ fieldtype: "HTML", options: `<p>${__("Handlung")}: <b>${spec.label}</b><br>
						${__("Bedeutung")}: <b>${spec.meaning}</b><br>
						${__("Datensatz")}: <span class="rw-mono">${frappe.utils.escape_html(document_name)}</span></p>` },
					{
						fieldname: "reason",
						fieldtype: "Small Text",
						label: __("Begründung"),
						reqd: spec.reason ? 1 : 0,
						hidden: spec.reason ? 0 : 1,
					},
					{
						fieldname: "password",
						fieldtype: "Password",
						label: __("Kennwort zur Bestätigung"),
						reqd: 1,
						description: __("Das Kennwort wird nur zur Bestätigung geprüft und nicht gespeichert."),
					},
				],
				primary_action_label: __("Unterzeichnen"),
				primary_action: (values) => {
					dialog.set_primary_action(__("Wird unterzeichnet …"), () => {});
					dialog.get_primary_btn().prop("disabled", true);
					frappe
						.call("rheinwerk_mes.compliance.esignature.sign", {
							document_type,
							document_name,
							act,
							password: values.password,
							reason: values.reason,
							transition,
						})
						.then((response) => {
							dialog.hide();
							frappe.show_alert({ message: __("Unterschrift erteilt: {0}", [response.message]), indicator: "green" });
							resolve(response.message);
						})
						.catch((error) => {
							dialog.get_primary_btn().prop("disabled", false);
							dialog.set_primary_action(__("Unterzeichnen"), dialog.primary_action);
							reject(error);
						});
				},
			});
			dialog.show();
			dialog.$wrapper.find('[data-fieldname="password"] input').focus();
		});
	},
};
