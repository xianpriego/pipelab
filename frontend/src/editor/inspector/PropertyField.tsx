import type { ReactNode } from "react";
import type { PropertyInfo, PropertyValue } from "../../api/types";
import { Icon } from "../../components/Icon";
import { NUMBER_TYPES, isLiveEditable } from "../../lib/propertyValues";
import { BooleanField } from "./fields/BooleanField";
import { EnumField } from "./fields/EnumField";
import { FlagsField } from "./fields/FlagsField";
import { NumberField } from "./fields/NumberField";
import { PadField } from "./fields/PadField";
import { TextField } from "./fields/TextField";
import type { FieldProps } from "./fields/types";

interface PropertyFieldProps {
  prop: PropertyInfo;
  value: PropertyValue | undefined;
  running: boolean;
  pads: string[];
  onChange: (value: PropertyValue | undefined) => void;
  onTryLive?: () => void;
  extra?: ReactNode;
}

function Widget(props: FieldProps & { pads: string[] }) {
  const { prop } = props;
  if (prop.type === "boolean") return <BooleanField {...props} />;
  if (NUMBER_TYPES.has(prop.type)) return <NumberField {...props} />;
  if (prop.type === "enum") return <EnumField {...props} />;
  if (prop.type === "flags") return <FlagsField {...props} />;
  if (prop.type === "pad") return <PadField {...props} />;
  return <TextField {...props} />;
}

function LiveBadge({ prop, running, onTryLive }: Pick<PropertyFieldProps, "prop" | "running" | "onTryLive">) {
  if (!prop.writable) return <span className="badge">read-only</span>;
  if (prop.construct_only) return <span className="badge" title="Only settable when the element is created">construct</span>;
  if (isLiveEditable(prop)) {
    return (
      <span className={`badge${running ? " success" : ""}`} title="Can be changed while the pipeline is playing">
        <Icon name="zap" size={10} /> live
      </span>
    );
  }
  if (!running) return null;
  if (prop.mutable === "unknown" && onTryLive) {
    return (
      <button className="btn btn-sm try-live" onClick={onTryLive}
        title="The element does not declare whether this can change while playing. Apply it now anyway.">
        try live
      </button>
    );
  }
  return <span className="badge warning" title={`Changeable up to ${prop.mutable.toUpperCase()} state`}>restart</span>;
}

export function PropertyField({ prop, value, running, pads, onChange, onTryLive, extra }: PropertyFieldProps) {
  const modified = value !== undefined;
  const editable = prop.writable && prop.type !== "object" && prop.type !== "other";
  return (
    <div className={`prop-row${modified ? " modified" : ""}`}>
      <div className="prop-head">
        <span className="prop-name" title={prop.nick}>{prop.name}</span>
        <span className="prop-type faint">{prop.type === "enum" || prop.type === "flags" ? prop.value_type : prop.type}</span>
        <span className="spacer" />
        <LiveBadge prop={prop} running={running} onTryLive={onTryLive} />
        {extra}
        {modified ? (
          <button className="icon-btn prop-reset" title="Reset to default" aria-label={`Reset ${prop.name}`}
            onClick={() => onChange(undefined)}>
            <Icon name="refresh" size={12} />
          </button>
        ) : null}
      </div>
      {editable ? (
        <Widget prop={prop} value={value} onCommit={onChange} pads={pads} />
      ) : (
        <div className="prop-readonly mono">{value ?? String(prop.default ?? "—")}</div>
      )}
      {prop.blurb ? <div className="prop-blurb">{prop.blurb}</div> : null}
    </div>
  );
}
