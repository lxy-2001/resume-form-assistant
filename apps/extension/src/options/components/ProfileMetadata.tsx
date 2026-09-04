import type { ProfileSnapshot } from "../profileClient";

interface ProfileMetadataProps {
  snapshot: ProfileSnapshot;
}

export function ProfileMetadata({ snapshot }: ProfileMetadataProps) {
  return (
    <section aria-labelledby="profile-metadata-title">
      <h2 id="profile-metadata-title">资料状态</h2>
      <p>资料版本：{snapshot.profile_version}</p>
      <p>字段数量：{snapshot.fields.length}</p>
      <p>经历数量：{snapshot.records.length}</p>
      <p>最近更新：{snapshot.updated_at}</p>
    </section>
  );
}
