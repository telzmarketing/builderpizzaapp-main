import AdminCozinha from "./Cozinha";

/** KDS Esfiha uses the canonical touch workspace and multi-operator flow.
 * The station query keeps presence and production tasks scoped to esfiha. */
export default function KdsEsfiha() {
  return (
    <AdminCozinha
      station="esfiha"
      title="KDS Esfiha"
      pwaKey="kds-esfiha"
      startToastLabel="esfiha"
    />
  );
}
