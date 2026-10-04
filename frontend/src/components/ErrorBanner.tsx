export function ErrorBanner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      {onDismiss && (
        <button type="button" className="error-banner__close" onClick={onDismiss}>
          Dismiss
        </button>
      )}
    </div>
  )
}
