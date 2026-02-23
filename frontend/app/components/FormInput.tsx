import { ReactNode } from "react";

interface BaseFormInputProps {
  label?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
}

type InputProps = BaseFormInputProps & {
  as?: "input";
  type?: React.HTMLInputTypeAttribute;
  value: string | number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  step?: string;
} & Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "value" | "onChange" | "type" | "required" | "disabled" | "placeholder" | "step"
  >;

type SelectProps = BaseFormInputProps & {
  as: "select";
  value: string | number;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  children?: ReactNode;
} & Omit<
    React.SelectHTMLAttributes<HTMLSelectElement>,
    "value" | "onChange" | "required" | "disabled"
  >;

type TextareaProps = BaseFormInputProps & {
  as: "textarea";
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
} & Omit<
    React.TextareaHTMLAttributes<HTMLTextAreaElement>,
    "value" | "onChange" | "required" | "disabled" | "placeholder"
  >;

type FormInputProps = InputProps | SelectProps | TextareaProps;

export default function FormInput(props: FormInputProps) {
  const {
    label,
    placeholder,
    required = false,
    error,
  } = props;

  const baseClass = `input ${error ? "border-red-500 focus:border-red-500 focus:shadow-red-100" : ""}`;

  const renderField = () => {
    if (props.as === "select") {
      const { as: asProp, children, ...selectProps } = props;
      void asProp;
      return (
        <select className={baseClass} {...selectProps}>
          {children}
        </select>
      );
    }

    if (props.as === "textarea") {
      const { as: asProp, ...textareaProps } = props;
      void asProp;
      return (
        <textarea
          placeholder={placeholder}
          className={baseClass}
          {...textareaProps}
        />
      );
    }

    const { as: asProp, type = "text", step, ...inputProps } = props;
    void asProp;
    return (
      <input
        type={type}
        step={step}
        placeholder={placeholder}
        className={baseClass}
        {...inputProps}
      />
    );
  };

  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label className="text-sm font-medium text-gray-700">
          {label}
          {required && <span className="ml-1 text-red-500">*</span>}
        </label>
      )}
      {renderField()}
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
