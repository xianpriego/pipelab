import type { PropertyInfo, PropertyValue } from "../../../api/types";

export interface FieldProps {
  prop: PropertyInfo;
  value: PropertyValue | undefined;
  onCommit: (value: PropertyValue) => void;
  disabled?: boolean;
}
