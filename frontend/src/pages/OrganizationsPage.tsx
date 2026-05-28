import { FormEvent, useEffect, useMemo, useState } from "react";

import { PageGuide } from "../components/PageGuide";
import type { Organization, OrganizationAutofillSuggestion } from "../lib/types";
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
  onAutofillOrganization: (organizationId: string) => Promise<OrganizationAutofillSuggestion>;
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

function mergeSuggestionsIntoForm(current: FormState, suggestions: OrganizationAutofillSuggestion): FormState {
  const next = { ...current };
  const fields = [
    "name",
    "short_name",
    "inn",
    "kpp",
    "ogrn",
    "legal_address",
    "actual_address",
    "okved",
    "website",
    "email",
    "phone",
    "director_name",
    "responsible_person",
  ] as const;
  for (const field of fields) {
    const currentValue = (next[field] ?? "").trim();
    const suggestedValue = suggestions[field]?.trim() ?? "";
    if (!currentValue && suggestedValue) {
      next[field] = suggestedValue;
    }
  }
  return next;
}

export function OrganizationsPage({
  organizations,
  selectedOrganizationId,
  onSelectOrganization,
  onCreateOrganization,
  onUpdateOrganization,
  onDeleteOrganization,
  onAutofillOrganization,
}: Props) {
  const [createForm, setCreateForm] = useState<FormState>(EMPTY_FORM);
  const [editForm, setEditForm] = useState<FormState>(EMPTY_FORM);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [autofillMessage, setAutofillMessage] = useState<string | null>(null);
  const [autofillError, setAutofillError] = useState<string | null>(null);
  const [isAutofilling, setIsAutofilling] = useState(false);
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

  useEffect(() => {
    if (!isEditModalOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsEditModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isEditModalOpen]);

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
    setIsEditModalOpen(false);
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
    setIsEditModalOpen(false);
  }

  function updateCreateForm(field: keyof FormState, value: string) {
    setCreateForm((current) => ({ ...current, [field]: value }));
  }

  function updateEditForm(field: keyof FormState, value: string) {
    setEditForm((current) => ({ ...current, [field]: value }));
  }

  function handleOpenOrganization(organizationId: string) {
    onSelectOrganization(organizationId);
    setAutofillMessage(null);
    setAutofillError(null);
    setIsEditModalOpen(true);
  }

  async function handleAutofill() {
    if (!selectedOrganization) {
      return;
    }
    setIsAutofilling(true);
    setAutofillMessage(null);
    setAutofillError(null);
    try {
      const suggestions = await onAutofillOrganization(selectedOrganization.id);
      if (suggestions.matched_fields.length === 0) {
        setAutofillError("Система не нашла подходящих реквизитов. Сначала обработайте документы с реквизитами организации.");
        return;
      }
      setEditForm((current) => mergeSuggestionsIntoForm(current, suggestions));
      setAutofillMessage(
        `Подтянуто полей: ${suggestions.matched_fields.length}. Источники: ${suggestions.source_documents.slice(0, 3).join(", ")}${suggestions.source_documents.length > 3 ? " и другие" : ""}.`,
      );
    } catch (error) {
      setAutofillError(error instanceof Error ? error.message : "Не удалось подтянуть данные из документов.");
    } finally {
      setIsAutofilling(false);
    }
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
              onClick={() => handleOpenOrganization(organization.id)}
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

      {selectedOrganization && isEditModalOpen ? (
        <div className="modal-backdrop" onClick={() => setIsEditModalOpen(false)}>
          <section className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="section-header">
              <div>
                <p className="eyebrow">Карточка организации</p>
                <h2>Редактирование организации</h2>
              </div>
              <button type="button" className="modal-close" onClick={() => setIsEditModalOpen(false)} aria-label="Закрыть окно">
                ×
              </button>
            </div>
            <p className="helper-text">
              Здесь можно обновить реквизиты, контакты и ответственных лиц. Из этого же окна можно удалить тестовый
              контур целиком.
            </p>
            <div className="inline-actions modal-tools">
              <button type="button" className="action-button action-secondary" disabled={isAutofilling} onClick={() => void handleAutofill()}>
                {isAutofilling ? "Ищем во вложениях..." : "Попробовать из вложений"}
              </button>
            </div>
            {autofillMessage ? <div className="success-box">{autofillMessage}</div> : null}
            {autofillError ? <div className="error-box">{autofillError}</div> : null}
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
        </div>
      ) : null}
    </div>
  );
}
