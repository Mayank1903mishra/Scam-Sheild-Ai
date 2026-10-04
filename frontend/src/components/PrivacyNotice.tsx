export function PrivacyNotice() {
  return (
    <aside className="privacy-notice" aria-label="Privacy notice">
      <h2>Before you submit</h2>
      <ul>
        <li>
          Your input is analysed by the local ScamShield server only. Nothing is
          sent to external services, and submitted links are never opened.
        </li>
        <li>
          Screenshots are converted to text and the image file is deleted
          immediately afterwards; it is never shown or kept.
        </li>
        <li>
          Scans are stored for 30 days by default and can be deleted by you at
          any time from History.
        </li>
        <li>
          Do not paste passwords, one-time codes, or bank details - the
          analysis does not need them.
        </li>
        <li>
          Scores are heuristics, not proof of fraud. Risk indicators are not
          proof of fraud.
        </li>
      </ul>
    </aside>
  )
}
