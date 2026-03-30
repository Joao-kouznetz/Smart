interface QuantityStepperProps {
  label: string;
  value: number;
  onChange: (nextValue: number) => void;
  min?: number;
}

export function QuantityStepper({
  label,
  value,
  onChange,
  min = 1,
}: QuantityStepperProps) {
  const decrementDisabled = value <= min;

  return (
    <div className="quantity-stepper">
      <span className="quantity-stepper__label">{label}</span>
      <div className="quantity-stepper__controls">
        <button
          className="touch-button touch-button--ghost"
          disabled={decrementDisabled}
          onClick={() => onChange(Math.max(min, value - 1))}
          type="button"
        >
          -
        </button>
        <span className="quantity-stepper__value">{value}</span>
        <button
          className="touch-button touch-button--ghost"
          onClick={() => onChange(value + 1)}
          type="button"
        >
          +
        </button>
      </div>
    </div>
  );
}
