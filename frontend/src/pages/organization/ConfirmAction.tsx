/**
 * Confirmation for actions that end somebody's access.
 *
 * Why a typed confirmation rather than an "Are you sure?"
 * ------------------------------------------------------
 * Removing a member, demoting an owner, revoking an assignment and confirming
 * a migrated organization are all one click away from a list of similar-looking
 * rows, and all of them are felt by somebody else — usually while they are
 * mid-task. A yes/no dialog after a mis-click is answered reflexively, because
 * the reflex is what produced the click.
 *
 * Requiring the subject's name to be typed forces the reader to look at *which*
 * row they are acting on. That is the mistake this guards against: not "did you
 * mean to remove somebody", but "did you mean to remove this person".
 *
 * The reason field is separate and optional-by-policy: the backend accepts an
 * absent reason, and the interface asks for one anyway, because the audit line
 * is read months later by somebody who was not in the room.
 */

import { useEffect, useId, useState } from 'react';

import { Alert, Button, Dialog, TextField } from '../../design-system/components';

export interface ConfirmActionProps {
  open: boolean;
  title: string;
  /** What is about to happen, in a sentence. */
  description: React.ReactNode;
  /** The exact text the user must type. Usually a username or an email. */
  confirmPhrase: string;
  confirmLabel: string;
  /** Shown above the field. Consequences, not reassurance. */
  consequence?: React.ReactNode;
  busy?: boolean;
  error?: string | null;
  askForReason?: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
  testId?: string;
}

export function ConfirmAction({
  open, title, description, confirmPhrase, confirmLabel, consequence,
  busy = false, error = null, askForReason = true, onCancel, onConfirm,
  testId,
}: ConfirmActionProps) {
  const [typed, setTyped] = useState('');
  const [reason, setReason] = useState('');
  const fieldId = useId();

  // Reset whenever the dialog is opened for a different subject, so a phrase
  // typed for the previous row cannot arm the button for this one.
  useEffect(() => {
    if (open) {
      setTyped('');
      setReason('');
    }
  }, [open, confirmPhrase]);

  const armed = typed.trim() === confirmPhrase && !busy;

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      footer={(
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => onConfirm(reason.trim())}
            disabled={!armed}
            loading={busy}
            data-testid={testId ? `${testId}-confirm` : undefined}
          >
            {confirmLabel}
          </Button>
        </>
      )}
    >
      <div data-testid={testId}>
        <p>{description}</p>

        {consequence && (
          <Alert tone="warn" title="What this does">{consequence}</Alert>
        )}

        {error && (
          <Alert tone="danger" title="Not applied" role="alert">{error}</Alert>
        )}

        <TextField
          id={`${fieldId}-phrase`}
          label={`Type ${confirmPhrase} to confirm`}
          value={typed}
          autoComplete="off"
          onChange={(e) => setTyped(e.target.value)}
          help="Typing the name is deliberate: it makes you check which row you are acting on."
        />

        {askForReason && (
          <TextField
            id={`${fieldId}-reason`}
            label="Reason (recorded in the access history)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            help="Optional, but the audit line is read months later by somebody who was not here."
          />
        )}
      </div>
    </Dialog>
  );
}
