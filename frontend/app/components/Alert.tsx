import { AlertCircle, CheckCircle, AlertTriangle } from "lucide-react";

interface AlertProps {
  type: "success" | "error" | "warning";
  message: string;
  onClose?: () => void;
}

export default function Alert({ type, message, onClose }: AlertProps) {
  const styles = {
    success: "alert-success",
    error: "alert-danger",
    warning: "alert-warning",
  };

  const icons = {
    success: <CheckCircle size={20} />,
    error: <AlertCircle size={20} />,
    warning: <AlertTriangle size={20} />,
  };

  return (
    <div className={`alert ${styles[type]} fade-in`}>
      {icons[type]}
      <div className="flex-1">
        <p className="text-sm font-medium">{message}</p>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="text-xl leading-none opacity-70 hover:opacity-100"
        >
          ×
        </button>
      )}
    </div>
  );
}
