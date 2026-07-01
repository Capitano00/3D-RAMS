import { ShieldCheck } from "lucide-react";

export default function SafetyBoundaryRail() {
  return (
    <aside className="safety-boundary-rail">
      <ShieldCheck size={18} />
      <p>
        3D-RAMS is a pre-visit research and review aid. It does not produce certified RAMS, approve work,
        replace competent-person judgement, or provide emergency instructions. Verify evidence and site conditions
        before dispatch.
      </p>
    </aside>
  );
}
