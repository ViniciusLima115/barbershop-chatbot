import { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  color?: "blue" | "green" | "red" | "amber";
  trend?: "up" | "down";
}

export default function StatCard({
  label,
  value,
  icon,
  color = "blue",
  trend,
}: StatCardProps) {
  const colorClasses = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    red: "bg-red-50 text-red-600",
    amber: "bg-amber-50 text-amber-600",
  };

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{label}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
        </div>
        {icon && (
          <div className={`rounded-lg p-3 ${colorClasses[color]}`}>{icon}</div>
        )}
      </div>
      {trend && (
        <div className="mt-4 text-xs font-medium">
          {trend === "up" ? (
            <span className="text-green-600">↑ Aumentando</span>
          ) : (
            <span className="text-red-600">↓ Diminuindo</span>
          )}
        </div>
      )}
    </div>
  );
}
