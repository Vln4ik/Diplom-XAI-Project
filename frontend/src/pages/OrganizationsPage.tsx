import { FormEvent, useEffect, useMemo, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import type { Organization } from "../lib/types";
import { formatOrganizationType } from "../lib/ui";

type OrganizationFormPayload = {
  name: string;
  short_name?: string;
  inn?: string;
  kpp?: string;
  ogrn?: string;
  legal_address?: string;
  actual_address?: string;
  organization_type?: string;
  okved?: string;
  website?: string;
  email?: string;
  phone?: string;
  director_name?: string;
  responsible_person?: string;
};

type Props = {
  organizations: Organization[];
  selectedOrganizationId: string | null;
  onSelectOrganization: (organizationId: string) => void;
  onCreateOrganization: (payload: OrganizationFormPayload) => Promise<void>;
  onUpdateOrganization: (organizationId: string, payload: OrganizationFormPayload) => Promise<void>;
  onDeleteOrganization: (organizationId: string) => Promise<void>;
};

type FormState = {
  name: string;
  short_name: string;
  inn: string;
  kpp: string;
  ogrn: string;
  legal_address: string;
  actual_address: string;
  organization_type: string;
  okved: string;
  website: string;
  email: string;
  phone: string;
  director_name: string;
  responsible_person: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  short_name: "",
  inn: "",
  kpp: "",
  ogrn: "",
  legal_address: "",
  actual_address: "",
  organization_type: "educational",
  okved: "",
  website: "",
  email: "",
  phone: "",
  director_name: "",
  responsible_person: "",
};

function toFormState(organization: Organization | null): FormState {
  if (!organization) {
    return EMPTY_FORM;
  }
  return {
    name: organization.name ?? "",
    short_name: organization.short_name ?? "",
    inn: organization.inn ?? "",
    kpp: organization.kpp ?? "",
    ogrn: organization.ogrn ?? "",
    legal_address: organization.legal_address ?? "",
    actual_address: organization.actual_address ?? "",
    organization_type: organization.organization_type ?? "educational",
    okved: organization.okved ?? "",
    website: organization.website ?? "",
    email: organization.email ?? "",
    phone: organization.phone ?? "",
    director_name: organization.director_name ?? "",
    responsible_person: organization.responsible_person ?? "",
  };
}

function toPayload(form: FormState): OrganizationFormPayload {
  return {
    name: form.name.trim(),
    short_name: form.short_name.trim() || undefined,
    inn: form.inn.trim() || undefined,
    kpp: form.kpp.trim() || undefined,
    ogrn: form.ogrn.trim() || undefined,
    legal_address: form.legal_address.trim() || undefined,
    actual_address: form.actual_address.trim() || undefined,
    organization_type: form.organization_type,
    okved: form.okved.trim() || undefined,
    website: form.website.trim() || undefined,
    email: form.email.trim() || undefined,
    phone: form.phone.trim() || undefined,
    director_name: form.director_name.trim() || undefined,
    responsible_person: form.responsible_person.trim() || undefined,
  };
}

export function OrganizationsPage({
  organizations,
  selectedOrganizationId,
  onSelectOrganization,
  onCreateOrganization,
  onUpdateOrganization,
  onDeleteOrganization,
}: Props) {
  const [createForm, setCreateForm] = useState<FormState>(EMPTY_FORM);
  const [editForm, setEditForm] = useState<FormState>(EMPTY_FORM);
  const selectedOrganization = useMemo(
    () => organizations.find((organization) => organization.id === selectedOrganizationId) ?? null,
    [organizations, selectedOrganizationId],
  );

  useEffect(() => {
    if (!selectedOrganizationId && organizations.length > 0) {
      onSelectOrganization(organizations[0].id);
      return;
    }
    setEditForm(toFormState(selectedOrganization));
  }, [onSelectOrganization, organizations, selectedOrganization, selectedOrganizationId]);

  async function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!createForm.name.trim()) {
      return;
    }
    await onCreateOrganization(toPayload(createForm));
    setCreateForm(EMPTY_FORM);
  }

  async function handleUpdateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization || !editForm.name.trim()) {
      return;
    }
    await onUpdateOrganization(selectedOrganization.id, toPayload(editForm));
  }

  async function handleDelete() {
    if (!selectedOrganization) {
      return;
    }
    const shouldDelete = window.confirm(
      `Удалить организацию «${selectedOrganization.name}» вместе со связанными документами, отчетами и артефактами?`,
    );
    if (!shouldDelete) {
      return;
    }
    await onDeleteOrganization(selectedOrganization.id);
  }

  function updateCreateForm(field: keyof FormState, value: string) {
    setCreateForm((current) => ({ ...current, [field]: value }));
  }

  function updateEditForm(field: keyof FormState, value: string) {
    setEditForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <div className="stack">
      <PageGuide
        title="Организации"
        summary="Этот раздел нужен для первичной настройки карточки организации. Отсюда начинается весь сценарий: без выбранной организации нельзя загружать документы, создавать отчеты и получать аналитику."
        blocks={[
          {
            title: "Что вносить",
            points: [
              "Полное и краткое название организации, тип, сайт, email и телефон.",
              "Юридические реквизиты, адреса и ответственных лиц, если они нужны для сценария проверки.",
              "Отдельную организацию под каждый изолированный контур проверки или демо-сценарий.",
            ],
          },
          {
            title: "Что отсюда получать",
            points: [
              "Точку привязки для документов, отчетов, рисков и аудита.",
              "Возможность быстро открыть карточку организации, отредактировать реквизиты или удалить тестовый контур.",
            ],
          },
          {
            title: "Как оптимизировать",
            points: [
              "Не смешивать несколько сценариев в одной карточке организации.",
              "Сразу заполнять контакты и ответственных, чтобы XAI и отчетные артефакты были понятнее на защите.",
            ],
          },
        ]}
      />

      <section className="panel">
        <div className="section-header">
          <h2>Новая организация</h2>
        </div>
        <form className="form-grid organization-form-grid" onSubmit={handleCreateSubmit}>
          <input value={createForm.name} onChange={(event) => updateCreateForm("name", event.target.value)} placeholder="Полное название организации" />
          <input value={createForm.short_name} onChange={(event) => updateCreateForm("short_name", event.target.value)} placeholder="Краткое название" />
          <select value={createForm.organization_type} onChange={(event) => updateCreateForm("organization_type", event.target.value)}>
            <option value="educational">Образовательная организация</option>
            <option value="other">Иная организация</option>
          </select>
          <input value={createForm.website} onChange={(event) => updateCreateForm("website", event.target.value)} placeholder="Сайт" />
          <input value={createForm.email} onChange={(event) => updateCreateForm("email", event.target.value)} placeholder="Email" />
          <input value={createForm.phone} onChange={(event) => updateCreateForm("phone", event.target.value)} placeholder="Телефон" />
          <input value={createForm.inn} onChange={(event) => updateCreateForm("inn", event.target.value)} placeholder="ИНН" />
          <input value={createForm.kpp} onChange={(event) => updateCreateForm("kpp", event.target.value)} placeholder="КПП" />
          <input value={createForm.ogrn} onChange={(event) => updateCreateForm("ogrn", event.target.value)} placeholder="ОГРН" />
          <input value={createForm.okved} onChange={(event) => updateCreateForm("okved", event.target.value)} placeholder="ОКВЭД" />
          <input value={createForm.director_name} onChange={(event) => updateCreateForm("director_name", event.target.value)} placeholder="Руководитель" />
          <input
            value={createForm.responsible_person}
            onChange={(event) => updateCreateForm("responsible_person", event.target.value)}
            placeholder="Ответственный за подготовку"
          />
          <input
            className="field-span-2"
            value={createForm.legal_address}
            onChange={(event) => updateCreateForm("legal_address", event.target.value)}
            placeholder="Юридический адрес"
          />
          <input
            className="field-span-2"
            value={createForm.actual_address}
            onChange={(event) => updateCreateForm("actual_address", event.target.value)}
            placeholder="Фактический адрес"
          />
          <button type="submit" className="field-span-2">
            Создать организацию
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Организации</h2>
          <span>{organizations.length}</span>
        </div>
        <div className="list">
          {organizations.map((organization) => (
            <button
              key={organization.id}
              type="button"
              className={`organization-card ${selectedOrganizationId === organization.id ? "selected-row" : ""}`}
              onClick={() => onSelectOrganization(organization.id)}
            >
              <div>
                <strong>{organization.name}</strong>
                <p>{formatOrganizationType(organization.organization_type)}</p>
                <p className="helper-text">
                  {organization.short_name ? `${organization.short_name} · ` : ""}
                  {organization.website || organization.email || organization.phone || "Базовая карточка без контактов"}
                </p>
              </div>
              <span>{new Date(organization.updated_at).toLocaleDateString("ru-RU")}</span>
            </button>
          ))}
        </div>
      </section>

      {selectedOrganization ? (
        <section className="panel">
          <div className="section-header">
            <h2>Редактирование организации</h2>
            <span>{selectedOrganization.name}</span>
          </div>
          <p className="helper-text">
            Нажатие на карточку организации слева открывает эту форму с уже заполненными данными. Здесь можно обновить
            реквизиты или удалить тестовый контур целиком.
          </p>
          <form className="form-grid organization-form-grid" onSubmit={handleUpdateSubmit}>
            <input value={editForm.name} onChange={(event) => updateEditForm("name", event.target.value)} placeholder="Полное название организации" />
            <input value={editForm.short_name} onChange={(event) => updateEditForm("short_name", event.target.value)} placeholder="Краткое название" />
            <select value={editForm.organization_type} onChange={(event) => updateEditForm("organization_type", event.target.value)}>
              <option value="educational">Образовательная организация</option>
              <option value="other">Иная организация</option>
            </select>
            <input value={editForm.website} onChange={(event) => updateEditForm("website", event.target.value)} placeholder="Сайт" />
            <input value={editForm.email} onChange={(event) => updateEditForm("email", event.target.value)} placeholder="Email" />
            <input value={editForm.phone} onChange={(event) => updateEditForm("phone", event.target.value)} placeholder="Телефон" />
            <input value={editForm.inn} onChange={(event) => updateEditForm("inn", event.target.value)} placeholder="ИНН" />
            <input value={editForm.kpp} onChange={(event) => updateEditForm("kpp", event.target.value)} placeholder="КПП" />
            <input value={editForm.ogrn} onChange={(event) => updateEditForm("ogrn", event.target.value)} placeholder="ОГРН" />
            <input value={editForm.okved} onChange={(event) => updateEditForm("okved", event.target.value)} placeholder="ОКВЭД" />
            <input value={editForm.director_name} onChange={(event) => updateEditForm("director_name", event.target.value)} placeholder="Руководитель" />
            <input
              value={editForm.responsible_person}
              onChange={(event) => updateEditForm("responsible_person", event.target.value)}
              placeholder="Ответственный за подготовку"
            />
            <input
              className="field-span-2"
              value={editForm.legal_address}
              onChange={(event) => updateEditForm("legal_address", event.target.value)}
              placeholder="Юридический адрес"
            />
            <input
              className="field-span-2"
              value={editForm.actual_address}
              onChange={(event) => updateEditForm("actual_address", event.target.value)}
              placeholder="Фактический адрес"
            />
            <div className="inline-actions field-span-2">
              <button type="submit">Сохранить изменения</button>
              <button type="button" className="danger-button" onClick={handleDelete}>
                Удалить организацию
              </button>
            </div>
          </form>
        </section>
      ) : null}
    </div>
  );
}
