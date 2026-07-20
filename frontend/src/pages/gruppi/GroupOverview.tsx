import { useGroupContext } from "./GroupDetailLayout";

export function GroupOverview() {
  const { group } = useGroupContext();

  return <p className="sf-muted">{group.description}</p>;
}
