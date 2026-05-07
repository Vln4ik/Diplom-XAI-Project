import { FormEvent, useState } from "react";

import type { Organization } from "../lib/types";

type Props = {
  organizations: Organization[];
  onCreateOrganization: (payload: {
    name: string;
    short_name?: string;
    website?: string;
    email?: string;
    phone?: string;
  }) => Promise<void>;
};

export function OrganizationsPage({ organizations, onCreateOrganization }: Props) {
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [website, setWebsite] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }
    await onCreateOrganization({
      name: name.trim(),
      short_name: shortName.trim() || undefined,
      website: website.trim() || undefined,
      email: email.trim() || undefined,
      phone: phone.trim() || undefined,
    });
    setName("");
    setShortName("");
    setWebsite("");
    setEmail("");
    setPhone("");
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="section-header">
          <h2>Новая организация</h2>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Название организации" />
          <input value={shortName} onChange={(event) => setShortName(event.target.value)} placeholder="Краткое название" />
          <input value={website} onChange={(event) => setWebsite(event.target.value)} placeholder="Сайт" />
          <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" />
          <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Телефон" />
          <button type="submit">Создать организацию</button>
        </form>
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Организации</h2>
          <span>{organizations.length}</span>
        </div>
        <div className="list">
          {organizations.map((organization) => (
            <article key={organization.id} className="list-item">
              <div>
                <strong>{organization.name}</strong>
                <p>{organization.organization_type}</p>
              </div>
              <span>{new Date(organization.created_at).toLocaleDateString("ru-RU")}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
