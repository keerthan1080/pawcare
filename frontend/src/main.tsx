import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";

// Uses Vite same-origin /api/v1 proxy first; falls back to localhost:8000 if run standalone
const API_BASE = "/api/v1";
const FALLBACK_API_BASE = "http://localhost:8000/api/v1";
const BASE_PATH = "/pawCare";

type RoleKey = "PET_PARENT" | "CAREGIVER" | "ADMIN";
type AuthTabMode = "login" | "mobile_otp" | "register";

interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: RoleKey;
  is_active: boolean;
}

interface AuthSession {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
}

function syncBrowserPath(targetPath: string) {
  try {
    if (window.location.pathname !== targetPath) {
      window.history.replaceState({}, "", targetPath);
    }
  } catch {
    // Ignore history errors in restricted environments
  }
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    const res = await fetch(`${API_BASE}${path}`, init);
    if (res.status !== 502 && res.status !== 504) {
      return res;
    }
  } catch {
    // Fallback to direct localhost:8000 when running outside Vite proxy
  }
  return fetch(`${FALLBACK_API_BASE}${path}`, init);
}

/**
 * Hidden Developer Telemetry Logger:
 * Never surfaces raw server/network/infrastructure errors to end users.
 * Writes a structured trace with a unique trace_id to the browser DevTools console
 * and ships it asynchronously to `/api/v1/demo/client-logs` for backend developer inspection.
 */
function traceDeveloperError(component: string, operation: string, error: unknown, path?: string) {
  const traceId = "trc-" + Math.random().toString(16).slice(2, 10);
  const errorMessage = error instanceof Error ? error.message : String(error);
  const tracePayload = {
    trace_id: traceId,
    timestamp: new Date().toISOString(),
    component,
    operation,
    path: path || window.location.pathname,
    error_message: errorMessage,
  };
  console.error("[PawCare Developer Trace]", tracePayload);
  apiFetch("/demo/client-logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(tracePayload),
  }).catch(() => {});
}

function App() {
  // Authentication State (starts at clean /pawCare/login screen with empty inputs)
  const [session, setSession] = useState<AuthSession | null>(null);
  const [authMode, setAuthMode] = useState<AuthTabMode>("login");
  const [emailInput, setEmailInput] = useState<string>("");
  const [passwordInput, setPasswordInput] = useState<string>("");
  const [fullNameInput, setFullNameInput] = useState<string>("");
  const [phoneInput, setPhoneInput] = useState<string>("");
  const [registerRole, setRegisterRole] = useState<"PET_PARENT" | "CAREGIVER">("PET_PARENT");
  const [authLoading, setAuthLoading] = useState<boolean>(false);

  // Mobile Number OTP Sign-In State
  const [otpPhoneInput, setOtpPhoneInput] = useState<string>("");
  const [otpCodeInput, setOtpCodeInput] = useState<string>("");
  const [otpSent, setOtpSent] = useState<boolean>(false);
  const [otpRole, setOtpRole] = useState<"PET_PARENT" | "CAREGIVER">("PET_PARENT");
  const [otpFullName, setOtpFullName] = useState<string>("");

  // Federated OAuth / OIDC Modal State (Google Sign-In & Okta SSO)
  const [oauthProviderModal, setOauthProviderModal] = useState<"GOOGLE" | "OKTA" | null>(null);
  const [oauthEmailInput, setOauthEmailInput] = useState<string>("");
  const [oauthNameInput, setOauthNameInput] = useState<string>("");
  const [oauthRoleInput, setOauthRoleInput] = useState<"PET_PARENT" | "CAREGIVER">("PET_PARENT");
  const [oktaDomainInput, setOktaDomainInput] = useState<string>("https://pawcare.okta.com/oauth2/default");

  // Navigation & Domain State
  const [activeTab, setActiveTab] = useState<string>("discover");
  const [caregivers, setCaregivers] = useState<any[]>([]);
  const [pets, setPets] = useState<any[]>([]);
  const [emergencyInfo, setEmergencyInfo] = useState<any | null>(null);
  const [bookings, setBookings] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Filters
  const [serviceFilter, setServiceFilter] = useState<string>("");
  const [verifiedOnly, setVerifiedOnly] = useState<boolean>(false);
  const [maxPriceFilter, setMaxPriceFilter] = useState<string>("");

  // Booking Modal State
  const [selectedCaregiver, setSelectedCaregiver] = useState<any | null>(null);
  const [bookingServiceType, setBookingServiceType] = useState<string>("PET_BOARDING");
  const [startDate, setStartDate] = useState<string>("2026-11-20T09:00");
  const [endDate, setEndDate] = useState<string>("2026-11-22T09:00");
  const [specialInstructions, setSpecialInstructions] = useState<string>(
    "Please follow Bruno's 07:30 AM Breakfast, 08:00 AM Multivitamin, and 09:00 AM / 08:00 PM Walk routine."
  );
  const [quote, setQuote] = useState<any | null>(null);

  // Pet Owner Media Upload Form State
  const [newMediaType, setNewMediaType] = useState<"VIDEO" | "PHOTO">("VIDEO");
  const [newMediaTitle, setNewMediaTitle] = useState<string>("");
  const [newMediaUrl, setNewMediaUrl] = useState<string>("");
  const [newMediaNotes, setNewMediaNotes] = useState<string>("");

  // Admin Caretaker Selection State
  const [adminSelectedCaretaker, setAdminSelectedCaretaker] = useState<Record<string, string>>({});

  const showToast = (type: "success" | "error", text: string) => {
    setToast({ type, text });
    setTimeout(() => setToast(null), 4500);
  };

  // Ensure initial database seed & synchronize global /pawCare/login route
  useEffect(() => {
    apiFetch("/demo/seed", { method: "POST" }).catch((err) => {
      traceDeveloperError("AppInit", "seedWorkspace", err, "/api/v1/demo/seed");
    });
    syncBrowserPath(`${BASE_PATH}/login`);
  }, []);

  // Load role-permitted data & synchronize global /pawCare/ route whenever a user logs in
  useEffect(() => {
    if (!session) {
      syncBrowserPath(`${BASE_PATH}/login`);
      return;
    }
    syncBrowserPath(`${BASE_PATH}/`);
    const role = session.user.role;
    const token = session.access_token;

    fetchCaregivers();
    fetchBookings(token);

    if (role === "PET_PARENT") {
      setActiveTab("discover");
      fetchPetsAndEmergency(token);
    } else if (role === "CAREGIVER") {
      setActiveTab("bookings");
    } else if (role === "ADMIN") {
      setActiveTab("admin_queue");
      fetchNotifications(token);
      fetchAllUsers(token);
    }
  }, [session]);

  useEffect(() => {
    if (session) {
      fetchCaregivers();
    }
  }, [serviceFilter, verifiedOnly, maxPriceFilter]);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      const res = await apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailInput.trim(), password: passwordInput }),
      });
      const body = await res.json();
      if (!res.ok) {
        if (res.status === 401 || res.status === 403 || res.status === 422) {
          showToast("error", body.message || "Invalid email or password.");
        } else {
          traceDeveloperError("Auth", "login", body.message || `HTTP ${res.status}`, "/api/v1/auth/login");
        }
        return;
      }
      setSession(body);
      showToast("success", `Welcome back, ${body.user.full_name}!`);
    } catch (err) {
      traceDeveloperError("Auth", "loginNetworkFailure", err, "/api/v1/auth/login");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSendMobileOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpPhoneInput.trim()) return;
    setAuthLoading(true);
    try {
      const res = await apiFetch("/auth/otp/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: otpPhoneInput.trim(),
          role: otpRole,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        if (res.status >= 400 && res.status < 500) {
          showToast("error", body.message || "Please enter a valid 10-digit mobile number.");
        } else {
          traceDeveloperError("Auth", "sendOtp", body.message || `HTTP ${res.status}`, "/api/v1/auth/otp/send");
        }
        return;
      }
      setOtpSent(true);
      showToast("success", body.message || "6-digit verification code sent to your mobile number.");
    } catch (err) {
      traceDeveloperError("Auth", "sendOtpNetworkFailure", err, "/api/v1/auth/otp/send");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyMobileOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpPhoneInput.trim() || !otpCodeInput.trim()) return;
    setAuthLoading(true);
    try {
      const res = await apiFetch("/auth/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: otpPhoneInput.trim(),
          otp_code: otpCodeInput.trim(),
          full_name: otpFullName.trim() || undefined,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        if (res.status === 401 || res.status === 403 || res.status === 422 || res.status === 429) {
          showToast("error", body.message || "Invalid or expired 6-digit OTP code.");
        } else {
          traceDeveloperError("Auth", "verifyOtp", body.message || `HTTP ${res.status}`, "/api/v1/auth/otp/verify");
        }
        return;
      }
      setOtpSent(false);
      setOtpCodeInput("");
      setSession(body);
      showToast("success", `Signed in via Mobile OTP as ${body.user.full_name}!`);
    } catch (err) {
      traceDeveloperError("Auth", "verifyOtpNetworkFailure", err, "/api/v1/auth/otp/verify");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleFederatedOAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oauthProviderModal || !oauthEmailInput.trim()) return;
    setAuthLoading(true);
    const isOkta = oauthProviderModal === "OKTA";
    const endpoint = isOkta ? "/auth/oauth/okta" : "/auth/oauth/google";
    const payload = isOkta
      ? {
          id_token: `okta-oidc-assertion-${Date.now()}`,
          email: oauthEmailInput.trim(),
          full_name: oauthNameInput.trim() || oauthEmailInput.split("@")[0],
          okta_issuer: oktaDomainInput.trim() || "https://pawcare.okta.com/oauth2/default",
          role: oauthRoleInput,
        }
      : {
          id_token: `google-oidc-jwt-${Date.now()}`,
          email: oauthEmailInput.trim(),
          full_name: oauthNameInput.trim() || oauthEmailInput.split("@")[0],
          role: oauthRoleInput,
        };

    try {
      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        if (res.status >= 400 && res.status < 500) {
          showToast("error", body.message || `Unable to sign in with ${oauthProviderModal}.`);
        } else {
          traceDeveloperError("Auth", `oauth_${oauthProviderModal}`, body.message || `HTTP ${res.status}`, `/api/v1${endpoint}`);
        }
        return;
      }
      setOauthProviderModal(null);
      setOauthEmailInput("");
      setOauthNameInput("");
      setSession(body);
      showToast("success", `Signed in with ${isOkta ? "Okta SSO" : "Google"} as ${body.user.full_name}!`);
    } catch (err) {
      traceDeveloperError("Auth", `oauthNetworkFailure_${oauthProviderModal}`, err, `/api/v1${endpoint}`);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      const res = await apiFetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailInput.trim(),
          password: passwordInput,
          full_name: fullNameInput.trim(),
          phone: phoneInput.trim() || null,
          role: registerRole,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        if (res.status >= 400 && res.status < 500) {
          showToast("error", body.message || "Please check your registration details.");
        } else {
          traceDeveloperError("Auth", "register", body.message || `HTTP ${res.status}`, "/api/v1/auth/register");
        }
        return;
      }
      setSession(body);
      showToast("success", "Account created successfully!");
    } catch (err) {
      traceDeveloperError("Auth", "registerNetworkFailure", err, "/api/v1/auth/register");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setSession(null);
    setEmailInput("");
    setPasswordInput("");
    setOtpCodeInput("");
    setOtpSent(false);
    setPets([]);
    setBookings([]);
    setNotifications([]);
    setAllUsers([]);
    syncBrowserPath(`${BASE_PATH}/login`);
    showToast("success", "Signed out successfully.");
  };

  const fetchCaregivers = async () => {
    try {
      const params = new URLSearchParams();
      params.set("city", "Bengaluru");
      if (serviceFilter) params.set("service_type", serviceFilter);
      if (verifiedOnly) params.set("verified_only", "true");
      if (maxPriceFilter) params.set("max_price_inr", maxPriceFilter);

      const res = await apiFetch(`/caregivers?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setCaregivers(data.items || []);
      }
    } catch (err) {
      traceDeveloperError("Discovery", "fetchCaregivers", err, "/api/v1/caregivers");
    }
  };

  const fetchPetsAndEmergency = async (token: string) => {
    try {
      const res = await apiFetch("/pets", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const list = await res.json();
        setPets(list);
        if (list.length > 0) {
          const emRes = await apiFetch(`/pets/${list[0].id}/emergency-sheet`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (emRes.ok) {
            setEmergencyInfo(await emRes.json());
          }
        }
      }
    } catch (err) {
      traceDeveloperError("Pets", "fetchPetsAndEmergency", err, "/api/v1/pets");
    }
  };

  const fetchBookings = async (token: string) => {
    try {
      const res = await apiFetch("/bookings", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setBookings(await res.json());
      }
    } catch (err) {
      traceDeveloperError("Bookings", "fetchBookings", err, "/api/v1/bookings");
    }
  };

  const fetchNotifications = async (token: string) => {
    try {
      const res = await apiFetch("/notifications", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setNotifications(await res.json());
      }
    } catch (err) {
      traceDeveloperError("Notifications", "fetchNotifications", err, "/api/v1/notifications");
    }
  };

  const fetchAllUsers = async (token: string) => {
    try {
      const res = await apiFetch("/users?limit=50", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const body = await res.json();
        setAllUsers(body.items || []);
      }
    } catch (err) {
      traceDeveloperError("AdminUsers", "fetchAllUsers", err, "/api/v1/users");
    }
  };

  const openQuoteModal = async (caregiver: any) => {
    setSelectedCaregiver(caregiver);
    const defaultService = caregiver.services?.[0]?.service_type || "PET_BOARDING";
    setBookingServiceType(defaultService);
    await fetchQuote(caregiver.id, defaultService, startDate, endDate);
  };

  const fetchQuote = async (cgId: string, svcType: string, start: string, end: string) => {
    try {
      const params = new URLSearchParams({
        service_type: svcType,
        start_time: new Date(start).toISOString(),
        end_time: new Date(end).toISOString(),
      });
      const res = await apiFetch(`/caregivers/${cgId}/quote?${params.toString()}`);
      if (res.ok) {
        setQuote(await res.json());
      } else {
        setQuote(null);
      }
    } catch (err) {
      traceDeveloperError("Discovery", "fetchQuote", err, `/api/v1/caregivers/${cgId}/quote`);
      setQuote(null);
    }
  };

  const handleCreateBooking = async () => {
    if (!session || !selectedCaregiver || pets.length === 0) return;
    try {
      const createRes = await apiFetch("/bookings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          caregiver_id: selectedCaregiver.id,
          pet_id: pets[0].id,
          service_type: bookingServiceType,
          start_time: new Date(startDate).toISOString(),
          end_time: new Date(endDate).toISOString(),
          special_instructions: specialInstructions,
        }),
      });
      const body = await createRes.json();
      if (!createRes.ok) {
        if (createRes.status >= 400 && createRes.status < 500) {
          showToast("error", body.message || "Selected slot is unavailable.");
        } else {
          traceDeveloperError("Bookings", "createBooking", body.message, "/api/v1/bookings");
        }
        return;
      }
      setSelectedCaregiver(null);
      await fetchBookings(session.access_token);
      setActiveTab("bookings");
      showToast(
        "success",
        `Booking #${body.id.slice(0, 8)} submitted! Admin has been notified via WhatsApp to review your pet videos/photos and assign your Caretaker.`
      );
    } catch (err) {
      traceDeveloperError("Bookings", "createBookingNetworkFailure", err, "/api/v1/bookings");
    }
  };

  const handleAddPetMedia = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || pets.length === 0 || !newMediaTitle.trim() || !newMediaUrl.trim()) return;
    try {
      const res = await apiFetch(`/pets/${pets[0].id}/media`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          media_type: newMediaType,
          title: newMediaTitle.trim(),
          url: newMediaUrl.trim(),
          duration_seconds: newMediaType === "VIDEO" ? 30 : null,
          notes: newMediaNotes.trim() || null,
        }),
      });
      if (res.ok) {
        setNewMediaTitle("");
        setNewMediaUrl("");
        setNewMediaNotes("");
        await fetchPetsAndEmergency(session.access_token);
        showToast("success", `Added ${newMediaType} to ${pets[0].name}'s profile for Admin review!`);
      } else {
        const err = await res.json();
        traceDeveloperError("Pets", "addPetMedia", err.message, `/api/v1/pets/${pets[0].id}/media`);
      }
    } catch (err) {
      traceDeveloperError("Pets", "addPetMediaNetworkFailure", err, `/api/v1/pets/${pets[0]?.id}/media`);
    }
  };

  const handleAdminConfirmPayment = async (bookingId: string) => {
    if (!session || session.user.role !== "ADMIN") return;
    try {
      const res = await apiFetch(`/bookings/${bookingId}/admin-confirm-payment`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          media_reviewed: true,
          review_notes: "Admin inspected pet owner's videos & photos; payment confirmed.",
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        traceDeveloperError("Admin", "confirmPayment", body.message, `/api/v1/bookings/${bookingId}/admin-confirm-payment`);
        return;
      }
      await Promise.all([
        fetchBookings(session.access_token),
        fetchNotifications(session.access_token),
      ]);
      showToast("success", "Payment confirmed by Admin after reviewing Pet Owner videos & photos!");
    } catch (err) {
      traceDeveloperError("Admin", "confirmPaymentNetworkFailure", err, `/api/v1/bookings/${bookingId}/admin-confirm-payment`);
    }
  };

  const handleAdminAssignCaretaker = async (booking: any) => {
    if (!session || session.user.role !== "ADMIN") return;
    const chosenCgId = adminSelectedCaretaker[booking.id] || booking.caregiver_id;
    try {
      const res = await apiFetch(`/bookings/${booking.id}/admin-assign-caregiver`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          caregiver_id: chosenCgId,
          assignment_notes: "Caretaker assigned by Admin after detailed profile & media review.",
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        traceDeveloperError("Admin", "assignCaretaker", body.message, `/api/v1/bookings/${booking.id}/admin-assign-caregiver`);
        return;
      }
      await Promise.all([
        fetchBookings(session.access_token),
        fetchNotifications(session.access_token),
      ]);
      showToast("success", `Caretaker ${body.caregiver_name} assigned & WhatsApp confirmation sent!`);
    } catch (err) {
      traceDeveloperError("Admin", "assignCaretakerNetworkFailure", err, `/api/v1/bookings/${booking.id}/admin-assign-caregiver`);
    }
  };

  const handleTransitionStatus = async (bookingId: string, targetStatus: string) => {
    if (!session) return;
    try {
      const res = await apiFetch(`/bookings/${bookingId}/status`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          target_status: targetStatus,
          reason: `Updated to ${targetStatus} via PawCare Web UI`,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        traceDeveloperError("Bookings", "transitionStatus", data.message, `/api/v1/bookings/${bookingId}/status`);
        return;
      }
      await fetchBookings(session.access_token);
      showToast("success", `Booking status updated to ${targetStatus}`);
    } catch (err) {
      traceDeveloperError("Bookings", "transitionStatusNetworkFailure", err, `/api/v1/bookings/${bookingId}/status`);
    }
  };

  const handleAdminVerifyCaregiver = async (caregiverId: string, newStatus: "VERIFIED" | "REJECTED") => {
    if (!session || session.user.role !== "ADMIN") return;
    try {
      const res = await apiFetch(`/caregivers/${caregiverId}/verification-status`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          verification_status: newStatus,
          review_notes: "Reviewed by Admin in Web Console",
        }),
      });
      if (res.ok) {
        await fetchCaregivers();
        showToast("success", `Caregiver verification status updated to ${newStatus}`);
      } else {
        const err = await res.json();
        traceDeveloperError("Admin", "verifyCaregiver", err.message, `/api/v1/caregivers/${caregiverId}/verification-status`);
      }
    } catch (err) {
      traceDeveloperError("Admin", "verifyCaregiverNetworkFailure", err, `/api/v1/caregivers/${caregiverId}/verification-status`);
    }
  };

  // ============================================================================
  // SCREEN 1: PRODUCTION-CLEAN MULTI-PROVIDER LOGIN GATE (/pawCare/login)
  // Supports Email/Password, Mobile Number OTP, Google Sign-In, and Okta SSO
  // ============================================================================
  if (!session) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-950 via-purple-900 to-slate-900 flex flex-col justify-center items-center px-4 py-10">
        {toast && (
          <div className="fixed bottom-5 right-5 z-50 max-w-md">
            <div
              className={`px-4 py-3 rounded-xl shadow-lg border text-sm font-semibold flex items-center gap-2 ${
                toast.type === "success"
                  ? "bg-emerald-900 text-white border-emerald-700"
                  : "bg-rose-900 text-white border-rose-700"
              }`}
            >
              <span>{toast.type === "success" ? "✓" : "⚠"}</span>
              <span>{toast.text}</span>
            </div>
          </div>
        )}

        <div className="max-w-md w-full bg-white rounded-3xl shadow-2xl border border-purple-100 overflow-hidden">
          <div className="bg-purple-800 px-6 py-6 text-center text-white">
            <div className="w-12 h-12 rounded-2xl bg-white/15 mx-auto flex items-center justify-center text-2xl mb-2">
              🐾
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight">PawCare</h1>
            <p className="text-xs text-purple-200 font-medium mt-0.5">
              Book • Care • Stay Connected
            </p>
          </div>

          <div className="p-6 sm:p-8 space-y-5">
            {/* Auth Method Switcher: Email Sign In | Mobile OTP | Create Account */}
            <div className="grid grid-cols-3 bg-slate-100 p-1 rounded-xl gap-1">
              <button
                type="button"
                onClick={() => setAuthMode("login")}
                className={`py-2 rounded-lg text-xs font-bold transition ${
                  authMode === "login" ? "bg-white text-purple-800 shadow-xs" : "text-slate-600"
                }`}
              >
                Email Sign In
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("mobile_otp")}
                className={`py-2 rounded-lg text-xs font-bold transition ${
                  authMode === "mobile_otp" ? "bg-white text-purple-800 shadow-xs" : "text-slate-600"
                }`}
              >
                Mobile OTP
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("register")}
                className={`py-2 rounded-lg text-xs font-bold transition ${
                  authMode === "register" ? "bg-white text-purple-800 shadow-xs" : "text-slate-600"
                }`}
              >
                Create Account
              </button>
            </div>

            {/* MODE 1: EMAIL & PASSWORD SIGN IN */}
            {authMode === "login" && (
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    required
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-600"
                    placeholder="Enter your email"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Password</label>
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    required
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-600"
                    placeholder="Enter your password"
                  />
                </div>
                <button
                  type="submit"
                  disabled={authLoading}
                  className="w-full bg-purple-700 hover:bg-purple-800 text-white font-bold text-sm py-3 rounded-xl shadow-md transition"
                >
                  {authLoading ? "Signing in..." : "Sign In"}
                </button>
              </form>
            )}

            {/* MODE 2: MOBILE NUMBER OTP SIGN-IN */}
            {authMode === "mobile_otp" && (
              <div className="space-y-4">
                {!otpSent ? (
                  <form onSubmit={handleSendMobileOtp} className="space-y-3.5">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">Mobile Number</label>
                      <input
                        type="tel"
                        value={otpPhoneInput}
                        onChange={(e) => setOtpPhoneInput(e.target.value)}
                        required
                        className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-600"
                        placeholder="+91-9876543210"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">Account Type (for new numbers)</label>
                      <select
                        value={otpRole}
                        onChange={(e) => setOtpRole(e.target.value as "PET_PARENT" | "CAREGIVER")}
                        className="w-full text-sm border border-slate-300 rounded-xl px-3 py-2.5 bg-white font-semibold"
                      >
                        <option value="PET_PARENT">Pet Parent</option>
                        <option value="CAREGIVER">Caretaker</option>
                      </select>
                    </div>
                    <button
                      type="submit"
                      disabled={authLoading}
                      className="w-full bg-purple-700 hover:bg-purple-800 text-white font-bold text-sm py-3 rounded-xl shadow-md transition"
                    >
                      {authLoading ? "Sending OTP..." : "Send 6-Digit OTP"}
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleVerifyMobileOtp} className="space-y-3.5">
                    <div className="bg-purple-50 border border-purple-100 rounded-xl p-3 text-xs text-purple-900 flex items-center justify-between">
                      <span>Code sent to <strong>{otpPhoneInput}</strong></span>
                      <button
                        type="button"
                        onClick={() => setOtpSent(false)}
                        className="text-purple-700 font-bold underline"
                      >
                        Change
                      </button>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">6-Digit Verification Code (OTP)</label>
                      <input
                        type="text"
                        maxLength={6}
                        value={otpCodeInput}
                        onChange={(e) => setOtpCodeInput(e.target.value)}
                        required
                        className="w-full text-center tracking-widest font-extrabold text-base border border-slate-300 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-purple-600"
                        placeholder="••••••"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">Your Name (optional if already registered)</label>
                      <input
                        type="text"
                        value={otpFullName}
                        onChange={(e) => setOtpFullName(e.target.value)}
                        className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2"
                        placeholder="Full Name"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={authLoading}
                      className="w-full bg-purple-700 hover:bg-purple-800 text-white font-bold text-sm py-3 rounded-xl shadow-md transition"
                    >
                      {authLoading ? "Verifying OTP..." : "Verify OTP & Sign In"}
                    </button>
                  </form>
                )}
              </div>
            )}

            {/* MODE 3: CREATE ACCOUNT */}
            {authMode === "register" && (
              <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Full Name</label>
                  <input
                    type="text"
                    value={fullNameInput}
                    onChange={(e) => setFullNameInput(e.target.value)}
                    required
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2"
                    placeholder="Your Full Name"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    required
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2"
                    placeholder="you@example.com"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-600 mb-1">Phone</label>
                    <input
                      type="text"
                      value={phoneInput}
                      onChange={(e) => setPhoneInput(e.target.value)}
                      className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2"
                      placeholder="+91-9876543210"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-600 mb-1">Account Type</label>
                    <select
                      value={registerRole}
                      onChange={(e) => setRegisterRole(e.target.value as "PET_PARENT" | "CAREGIVER")}
                      className="w-full text-sm border border-slate-300 rounded-xl px-3 py-2 bg-white font-semibold"
                    >
                      <option value="PET_PARENT">Pet Parent</option>
                      <option value="CAREGIVER">Caretaker</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Password</label>
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    required
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2"
                    placeholder="At least 8 characters"
                  />
                </div>
                <button
                  type="submit"
                  disabled={authLoading}
                  className="w-full bg-purple-700 hover:bg-purple-800 text-white font-bold text-sm py-3 rounded-xl shadow-md transition"
                >
                  {authLoading ? "Creating account..." : "Create Account"}
                </button>
              </form>
            )}

            {/* ENTERPRISE & SOCIAL FEDERATED SIGN-IN: GOOGLE & OKTA SSO */}
            <div className="pt-2">
              <div className="relative flex py-2 items-center">
                <div className="flex-grow border-t border-slate-200"></div>
                <span className="flex-shrink mx-3 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Or continue with
                </span>
                <div className="flex-grow border-t border-slate-200"></div>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => {
                    setOauthProviderModal("GOOGLE");
                    setOauthEmailInput("");
                    setOauthNameInput("");
                  }}
                  className="flex items-center justify-center gap-2 border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold text-xs py-2.5 px-3 rounded-xl transition shadow-2xs"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path
                      fill="#EA4335"
                      d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.4 1 3.5 3.6 1.6 7.4l3.7 2.8C6.2 7.2 8.9 5 12 5z"
                    />
                    <path
                      fill="#4285F4"
                      d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.6l3.7 2.9c2.2-2 3.7-5 3.7-8.7z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.3 14.8c-.2-.8-.4-1.6-.4-2.5s.2-1.7.4-2.5L1.6 7C.6 9 0 11.2 0 13.5s.6 4.5 1.6 6.5l3.7-2.9z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 24c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.1 0-5.8-2.1-6.7-5l-3.7 2.8C3.5 20.9 7.4 24 12 24z"
                    />
                  </svg>
                  <span>Google</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setOauthProviderModal("OKTA");
                    setOauthEmailInput("");
                    setOauthNameInput("");
                  }}
                  className="flex items-center justify-center gap-2 border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold text-xs py-2.5 px-3 rounded-xl transition shadow-2xs"
                >
                  <span className="w-4 h-4 rounded-full border-4 border-indigo-700 inline-block"></span>
                  <span>Okta SSO</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* GOOGLE SIGN-IN / OKTA OIDC FEDERATED LOGIN MODAL */}
        {oauthProviderModal && (
          <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2.5">
                  {oauthProviderModal === "GOOGLE" ? (
                    <span className="w-8 h-8 rounded-lg bg-red-50 text-red-600 font-extrabold flex items-center justify-center text-sm">
                      G
                    </span>
                  ) : (
                    <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 font-extrabold flex items-center justify-center text-sm">
                      O
                    </span>
                  )}
                  <div>
                    <h3 className="text-base font-extrabold text-slate-900">
                      {oauthProviderModal === "GOOGLE" ? "Sign in with Google" : "Sign in with Okta SSO"}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {oauthProviderModal === "GOOGLE"
                        ? "Google OAuth 2.0 / OIDC Identity Provider"
                        : "Okta Enterprise OpenID Connect (OIDC)"}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setOauthProviderModal(null)}
                  className="text-slate-400 hover:text-slate-700 font-bold"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleFederatedOAuthSubmit} className="space-y-3.5">
                {oauthProviderModal === "OKTA" && (
                  <div>
                    <label className="block text-xs font-bold text-slate-600 mb-1">Okta Organization Issuer URL</label>
                    <input
                      type="url"
                      value={oktaDomainInput}
                      onChange={(e) => setOktaDomainInput(e.target.value)}
                      required
                      className="w-full text-xs border border-slate-300 rounded-xl px-3.5 py-2 bg-slate-50"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">
                    {oauthProviderModal === "GOOGLE" ? "Google Account Email" : "Okta Enterprise Email"}
                  </label>
                  <input
                    type="email"
                    value={oauthEmailInput}
                    onChange={(e) => setOauthEmailInput(e.target.value)}
                    required
                    placeholder={oauthProviderModal === "GOOGLE" ? "you@gmail.com" : "name@company.com"}
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2.5"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Full Name</label>
                  <input
                    type="text"
                    value={oauthNameInput}
                    onChange={(e) => setOauthNameInput(e.target.value)}
                    placeholder="Your Full Name"
                    className="w-full text-sm border border-slate-300 rounded-xl px-3.5 py-2"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Role (for new accounts)</label>
                  <select
                    value={oauthRoleInput}
                    onChange={(e) => setOauthRoleInput(e.target.value as "PET_PARENT" | "CAREGIVER")}
                    className="w-full text-sm border border-slate-300 rounded-xl px-3 py-2 bg-white font-semibold"
                  >
                    <option value="PET_PARENT">Pet Parent</option>
                    <option value="CAREGIVER">Caretaker</option>
                  </select>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setOauthProviderModal(null)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={authLoading}
                    className="bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold px-5 py-2.5 rounded-xl shadow-sm"
                  >
                    {authLoading
                      ? "Authenticating..."
                      : `Continue with ${oauthProviderModal === "GOOGLE" ? "Google" : "Okta SSO"}`}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ============================================================================
  // SCREEN 2: ROLE-GATED WORKSPACE (/pawCare/)
  // ============================================================================
  const role = session.user.role;
  const bruno = pets[0];
  const verifiedCaregivers = caregivers.filter((c) => c.is_verified_badge);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Header with Strict Role-Scoped Tabs */}
      <header className="bg-white border-b border-purple-100 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-700 text-white flex items-center justify-center font-extrabold text-lg shadow-sm">
              🐾
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-extrabold text-purple-900 tracking-tight">PawCare</span>
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-900">
                  {role}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">Book • Care • Stay Connected</p>
            </div>
          </div>

          {/* Role-Gated Navigation Bar: Users NEVER see Admin Tabs */}
          <nav className="flex flex-wrap items-center gap-1 bg-slate-100 p-1 rounded-xl">
            {role === "PET_PARENT" && (
              <>
                <button
                  onClick={() => setActiveTab("discover")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "discover" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Find Care
                </button>
                <button
                  onClick={() => setActiveTab("pet")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "pet" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  My Pet Profile &amp; Videos ({bruno?.media_gallery?.length || 0})
                </button>
                <button
                  onClick={() => setActiveTab("bookings")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "bookings" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  My Bookings ({bookings.length})
                </button>
              </>
            )}

            {role === "CAREGIVER" && (
              <>
                <button
                  onClick={() => setActiveTab("bookings")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "bookings" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Assigned Bookings ({bookings.length})
                </button>
                <button
                  onClick={() => setActiveTab("discover")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "discover" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Caregiver Directory
                </button>
              </>
            )}

            {role === "ADMIN" && (
              <>
                <button
                  onClick={() => setActiveTab("admin_queue")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "admin_queue" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Booking Review &amp; Caretaker Assignment ({bookings.length})
                </button>
                <button
                  onClick={() => setActiveTab("admin_whatsapp")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "admin_whatsapp" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  WhatsApp Alerts ({notifications.length})
                </button>
                <button
                  onClick={() => setActiveTab("admin_verify")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "admin_verify" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Caregiver Verification ({caregivers.length})
                </button>
                <button
                  onClick={() => setActiveTab("admin_users")}
                  className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition ${
                    activeTab === "admin_users" ? "bg-white text-purple-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Users ({allUsers.length})
                </button>
              </>
            )}
          </nav>

          {/* Logged-In User Identity & Logout */}
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-extrabold text-slate-900">{session.user.full_name}</p>
              <p className="text-[11px] text-slate-500">{session.user.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-700 font-bold text-xs px-3.5 py-2 rounded-xl border border-slate-200 transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 max-w-md">
          <div
            className={`px-4 py-3 rounded-xl shadow-lg border text-sm font-semibold flex items-center gap-2 ${
              toast.type === "success"
                ? "bg-emerald-900 text-white border-emerald-700"
                : "bg-rose-900 text-white border-rose-700"
            }`}
          >
            <span>{toast.type === "success" ? "✓" : "⚠"}</span>
            <span>{toast.text}</span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 flex-1">
        {/* PET PARENT VIEW: DISCOVER CAREGIVERS */}
        {activeTab === "discover" && (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-purple-900 via-purple-800 to-indigo-900 rounded-2xl p-6 sm:p-8 text-white shadow-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div className="max-w-2xl">
                <span className="inline-block text-xs font-bold uppercase tracking-wider bg-purple-700/80 text-amber-300 px-3 py-1 rounded-full mb-3">
                  Welcome, {session.user.full_name}
                </span>
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight mb-2">
                  Book Trusted Pet Care in Bengaluru
                </h1>
                <p className="text-purple-100 text-sm sm:text-base">
                  When you book, Admin receives an instant WhatsApp notification, reviews your pet's uploaded videos &amp; photos, confirms payment, and assigns your Caretaker.
                </p>
              </div>
            </div>

            {/* Filter Bar */}
            <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex flex-wrap items-center gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Service Type</label>
                <select
                  value={serviceFilter}
                  onChange={(e) => setServiceFilter(e.target.value)}
                  className="text-sm border border-slate-300 rounded-lg px-3 py-2 bg-white"
                >
                  <option value="">All 5 MVP Services</option>
                  <option value="PET_BOARDING">Pet Boarding</option>
                  <option value="IN_HOME_PET_SITTING">In-Home Pet Sitting</option>
                  <option value="DROP_IN_VISITS">Drop-In Visits</option>
                  <option value="DOG_WALKING">Dog Walking</option>
                  <option value="DAY_CARE">Pet Day Care</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Max Price (₹)</label>
                <select
                  value={maxPriceFilter}
                  onChange={(e) => setMaxPriceFilter(e.target.value)}
                  className="text-sm border border-slate-300 rounded-lg px-3 py-2 bg-white"
                >
                  <option value="">Any Price</option>
                  <option value="500">Up to ₹500</option>
                  <option value="900">Up to ₹900</option>
                  <option value="1200">Up to ₹1,200</option>
                </select>
              </div>

              <label className="flex items-center gap-2 text-sm font-semibold text-slate-700 cursor-pointer mt-4">
                <input
                  type="checkbox"
                  checked={verifiedOnly}
                  onChange={(e) => setVerifiedOnly(e.target.checked)}
                  className="rounded text-purple-700 focus:ring-purple-500 h-4 w-4"
                />
                <span>Verified Badge Only</span>
              </label>
            </div>

            {/* Caregiver Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {caregivers.map((cg) => (
                <div
                  key={cg.id}
                  className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition flex flex-col justify-between p-6"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div>
                        <h3 className="text-lg font-bold text-slate-900">{cg.full_name}</h3>
                        <p className="text-xs font-medium text-slate-500">
                          📍 {cg.locality || cg.city}, {cg.city} • {cg.years_of_experience} yrs exp
                        </p>
                      </div>
                      {cg.is_verified_badge ? (
                        <span className="bg-emerald-100 text-emerald-800 border border-emerald-200 text-xs font-bold px-2.5 py-1 rounded-full">
                          ✓ Verified
                        </span>
                      ) : (
                        <span className="bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold px-2.5 py-1 rounded-full">
                          {cg.verification_status}
                        </span>
                      )}
                    </div>

                    <p className="text-sm text-slate-600 mb-4">{cg.bio}</p>

                    <div className="border-t border-slate-100 pt-3 space-y-1.5 mb-5">
                      <p className="text-xs font-bold text-slate-400 uppercase">Services &amp; Pricing</p>
                      {(cg.services || []).map((s: any) => (
                        <div key={s.id} className="flex items-center justify-between text-sm">
                          <span className="text-slate-700 font-medium">{s.service_type.replace(/_/g, " ")}</span>
                          <span className="font-bold text-purple-900">
                            ₹{s.price_inr} <span className="text-xs font-normal text-slate-500">/{s.price_unit.replace("PER_", "").toLowerCase()}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {role === "PET_PARENT" && (
                    <button
                      onClick={() => openQuoteModal(cg)}
                      disabled={!cg.is_verified_badge}
                      className={`w-full py-2.5 px-4 rounded-xl font-bold text-sm transition ${
                        cg.is_verified_badge
                          ? "bg-purple-700 hover:bg-purple-800 text-white shadow-sm"
                          : "bg-slate-100 text-slate-400 cursor-not-allowed"
                      }`}
                    >
                      {cg.is_verified_badge ? "Request Booking" : "Awaiting Verification"}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* PET PARENT VIEW: MY PET PROFILE & VIDEOS/PHOTOS */}
        {activeTab === "pet" && role === "PET_PARENT" && bruno && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <div>
                  <span className="text-xs font-bold uppercase text-purple-700 bg-purple-50 px-2.5 py-1 rounded-full">
                    Pet Profile &amp; Media
                  </span>
                  <h2 className="text-2xl font-extrabold text-slate-900 mt-1">
                    {bruno.name} ({bruno.breed})
                  </h2>
                  <p className="text-sm text-slate-500">
                    {bruno.species} • {bruno.gender} • {bruno.age_years} yrs • {bruno.weight_kg} kg
                  </p>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-bold uppercase text-slate-400 tracking-wider mb-3">
                  Uploaded Pet Videos &amp; Photos (Reviewed by Admin Before Payment Confirmation)
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                  {(bruno.media_gallery || []).map((m: any) => (
                    <div key={m.id} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50">
                      <span
                        className={`text-xs font-extrabold px-2 py-0.5 rounded ${
                          m.media_type === "VIDEO"
                            ? "bg-indigo-100 text-indigo-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {m.media_type === "VIDEO" ? "🎬 VIDEO" : "📷 PHOTO"}
                      </span>
                      <p className="font-bold text-slate-900 text-sm mt-1">{m.title}</p>
                      {m.notes && <p className="text-xs text-slate-600 mt-1">{m.notes}</p>}
                    </div>
                  ))}
                </div>

                <form onSubmit={handleAddPetMedia} className="bg-purple-50/50 border border-purple-100 rounded-xl p-4 space-y-3">
                  <p className="text-xs font-bold text-purple-900 uppercase">
                    + Upload / Attach Pet Video or Photo to Profile
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <select
                      value={newMediaType}
                      onChange={(e) => setNewMediaType(e.target.value as "VIDEO" | "PHOTO")}
                      className="text-xs border border-slate-300 rounded-lg px-3 py-2 bg-white font-semibold"
                    >
                      <option value="VIDEO">🎬 Video Clip</option>
                      <option value="PHOTO">📷 Photo</option>
                    </select>
                    <input
                      type="text"
                      placeholder="Title (e.g. Bruno Playtime Video)"
                      value={newMediaTitle}
                      onChange={(e) => setNewMediaTitle(e.target.value)}
                      className="text-xs border border-slate-300 rounded-lg px-3 py-2 bg-white"
                      required
                    />
                    <input
                      type="text"
                      placeholder="Media URL (e.g. https://.../video.mp4)"
                      value={newMediaUrl}
                      onChange={(e) => setNewMediaUrl(e.target.value)}
                      className="text-xs border border-slate-300 rounded-lg px-3 py-2 bg-white"
                      required
                    />
                  </div>
                  <div className="flex items-center gap-3">
                    <input
                      type="text"
                      placeholder="Notes for Admin & Caretaker (optional)"
                      value={newMediaNotes}
                      onChange={(e) => setNewMediaNotes(e.target.value)}
                      className="flex-1 text-xs border border-slate-300 rounded-lg px-3 py-2 bg-white"
                    />
                    <button
                      type="submit"
                      className="bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold px-4 py-2 rounded-lg shrink-0"
                    >
                      Add to Pet Profile
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {emergencyInfo && (
              <div className="bg-rose-50/60 rounded-2xl border border-rose-200 p-6 shadow-sm space-y-4 h-fit">
                <span className="inline-block text-xs font-extrabold uppercase tracking-wider bg-rose-600 text-white px-2.5 py-1 rounded-full">
                  Emergency Action Sheet
                </span>
                <div className="space-y-3 text-sm">
                  <div className="bg-white p-3.5 rounded-xl border border-rose-100">
                    <p className="text-xs font-bold text-slate-400 uppercase">1. Contact Pet Parent</p>
                    <p className="font-bold text-slate-900">{emergencyInfo.pet_parent.full_name}</p>
                    <p className="text-slate-600">{emergencyInfo.pet_parent.phone}</p>
                  </div>
                  {emergencyInfo.preferred_veterinarian && (
                    <div className="bg-white p-3.5 rounded-xl border border-rose-100">
                      <p className="text-xs font-bold text-slate-400 uppercase">2. Preferred Veterinarian</p>
                      <p className="font-bold text-slate-900">{emergencyInfo.preferred_veterinarian.clinic_name}</p>
                      <p className="text-slate-700">{emergencyInfo.preferred_veterinarian.vet_name}</p>
                      <p className="text-slate-600">{emergencyInfo.preferred_veterinarian.phone}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* PET PARENT & CARETAKER VIEW: MY BOOKINGS */}
        {activeTab === "bookings" && role !== "ADMIN" && (
          <div className="space-y-4">
            <div>
              <h2 className="text-xl font-extrabold text-slate-900">
                {role === "PET_PARENT" ? "My Pet Bookings" : "Assigned Caretaker Bookings"}
              </h2>
              <p className="text-sm text-slate-500">
                {role === "PET_PARENT"
                  ? "Track your booking status as Admin verifies your pet videos/photos, confirms payment, and assigns your Caretaker."
                  : "Manage bookings assigned to you by Admin after payment confirmation."}
              </p>
            </div>

            {bookings.length === 0 ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-slate-500">
                No bookings found for your account yet.
              </div>
            ) : (
              <div className="space-y-4">
                {bookings.map((b) => (
                  <div
                    key={b.id}
                    className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2.5">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-purple-100 text-purple-900">
                          {b.status}
                        </span>
                        <span className="text-sm font-bold text-slate-900">
                          {b.service_type.replace(/_/g, " ")} • Caretaker: {b.caregiver_name}
                        </span>
                        {b.media_reviewed_by_admin ? (
                          <span className="text-xs font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                            ✓ Videos/Photos Verified &amp; Payment Confirmed by Admin
                          </span>
                        ) : (
                          <span className="text-xs font-semibold bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                            ⏳ Under Admin Review
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500">
                        Pet: <strong>{b.pet_name}</strong> • Window: {new Date(b.start_time).toLocaleString()} → {new Date(b.end_time).toLocaleString()}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <div className="text-right mr-2">
                        <p className="text-lg font-extrabold text-slate-900">₹{b.total_price_inr}</p>
                      </div>
                      {role === "CAREGIVER" && b.status === "CONFIRMED" && (
                        <button
                          onClick={() => handleTransitionStatus(b.id, "IN_PROGRESS")}
                          className="bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold px-3.5 py-2 rounded-xl"
                        >
                          Start Care (IN_PROGRESS)
                        </button>
                      )}
                      {role === "CAREGIVER" && b.status === "IN_PROGRESS" && (
                        <button
                          onClick={() => handleTransitionStatus(b.id, "COMPLETED")}
                          className="bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold px-3.5 py-2 rounded-xl"
                        >
                          Complete Stay (COMPLETED)
                        </button>
                      )}
                      {role === "PET_PARENT" && ["PAYMENT_PENDING", "CONFIRMED"].includes(b.status) && (
                        <button
                          onClick={() => handleTransitionStatus(b.id, "CANCELLED")}
                          className="bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold px-3.5 py-2 rounded-xl"
                        >
                          Cancel Booking
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ADMIN ONLY VIEW 1: BOOKING REVIEW, MEDIA VERIFICATION & CARETAKER ASSIGNMENT */}
        {role === "ADMIN" && activeTab === "admin_queue" && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <div className="border-b border-slate-100 pb-3">
              <span className="text-xs font-extrabold uppercase tracking-wider bg-purple-100 text-purple-900 px-2.5 py-1 rounded-full">
                Admin Command Center
              </span>
              <h2 className="text-xl font-extrabold text-slate-900 mt-1">
                Booking Review, Pet Video/Photo Verification &amp; Caretaker Assignment
              </h2>
              <p className="text-sm text-slate-500">
                Inspect the Pet Owner's uploaded videos and photos first, confirm payment (<code>PAYMENT_PENDING → PAID</code>), and assign a verified Caretaker (<code>PAID → CONFIRMED</code>).
              </p>
            </div>

            {bookings.length === 0 ? (
              <p className="text-sm text-slate-500 py-8 text-center">No bookings submitted yet.</p>
            ) : (
              <div className="space-y-4">
                {bookings.map((b) => (
                  <div key={b.id} className="rounded-2xl border border-slate-200 p-5 bg-slate-50/60 space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-purple-700 text-white">
                            {b.status}
                          </span>
                          <span className="font-extrabold text-slate-900">
                            Booking #{b.id.slice(0, 8)} — {b.pet_name} ({b.service_type.replace(/_/g, " ")})
                          </span>
                          <span className="text-xs text-slate-500">
                            Owner: {b.pet_parent_name} ({b.pet_parent_phone})
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 mt-1">
                          Dates: {new Date(b.start_time).toLocaleString()} → {new Date(b.end_time).toLocaleString()} • Total:{" "}
                          <strong>₹{b.total_price_inr}</strong>
                        </p>
                      </div>
                      {b.whatsapp_notification_url && (
                        <a
                          href={b.whatsapp_notification_url}
                          target="_blank"
                          rel="noreferrer"
                          className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-3.5 py-2 rounded-xl"
                        >
                          💬 Open WhatsApp Alert ↗
                        </a>
                      )}
                    </div>

                    <div className="bg-white rounded-xl border border-slate-200 p-4">
                      <p className="text-xs font-bold uppercase text-slate-400 mb-2">
                        Pet Owner Uploaded Videos &amp; Photos ({b.pet_media?.length || 0} items attached)
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5">
                        {(b.pet_media || []).map((m: any) => (
                          <div key={m.id} className="p-2.5 rounded-lg border border-slate-100 bg-slate-50 text-xs">
                            <span className="font-extrabold text-purple-800">
                              {m.media_type === "VIDEO" ? "🎬 VIDEO" : "📷 PHOTO"}
                            </span>
                            <p className="font-bold text-slate-900 mt-0.5">{m.title}</p>
                            {m.notes && <p className="text-slate-500 text-[11px] mt-0.5">{m.notes}</p>}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-200">
                      <button
                        onClick={() => handleAdminConfirmPayment(b.id)}
                        disabled={b.status !== "PAYMENT_PENDING"}
                        className={`text-xs font-bold px-4 py-2 rounded-xl transition ${
                          b.status === "PAYMENT_PENDING"
                            ? "bg-amber-500 hover:bg-amber-600 text-slate-950 shadow-xs"
                            : "bg-slate-200 text-slate-500 cursor-not-allowed"
                        }`}
                      >
                        {b.media_reviewed_by_admin
                          ? "✓ Step 1 Done: Media Reviewed & Payment Confirmed"
                          : "Step 1: Confirm Payment After Video/Photo Review (PAID)"}
                      </button>

                      <div className="flex items-center gap-2">
                        <select
                          value={adminSelectedCaretaker[b.id] || b.caregiver_id}
                          onChange={(e) =>
                            setAdminSelectedCaretaker({ ...adminSelectedCaretaker, [b.id]: e.target.value })
                          }
                          disabled={b.status !== "PAID"}
                          className="text-xs border border-slate-300 rounded-xl px-3 py-2 bg-white font-semibold"
                        >
                          {verifiedCaregivers.map((cg) => (
                            <option key={cg.id} value={cg.id}>
                              Assign: {cg.full_name} ({cg.locality})
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => handleAdminAssignCaretaker(b)}
                          disabled={b.status !== "PAID"}
                          className={`text-xs font-bold px-4 py-2 rounded-xl transition ${
                            b.status === "PAID"
                              ? "bg-purple-700 hover:bg-purple-800 text-white shadow-xs"
                              : "bg-slate-200 text-slate-500 cursor-not-allowed"
                          }`}
                        >
                          Step 2: Assign Caretaker &amp; Confirm (CONFIRMED)
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ADMIN ONLY VIEW 2: WHATSAPP DISPATCH LOG */}
        {role === "ADMIN" && activeTab === "admin_whatsapp" && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-lg font-extrabold text-slate-900">
              WhatsApp Booking Notification Log ({notifications.length})
            </h3>
            <div className="space-y-3">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                >
                  <div>
                    <span className="text-xs font-extrabold bg-emerald-700 text-white px-2 py-0.5 rounded">
                      {n.channel} • {n.delivery_status}
                    </span>
                    <span className="ml-2 text-xs font-bold text-slate-700">
                      To {n.recipient_role} ({n.recipient_phone}) • {n.event_type}
                    </span>
                    <pre className="text-xs text-slate-700 whitespace-pre-wrap font-sans mt-1.5">
                      {n.message_body}
                    </pre>
                  </div>
                  <a
                    href={n.whatsapp_url}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold px-3.5 py-2 rounded-xl shrink-0"
                  >
                    Open in WhatsApp ↗
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ADMIN ONLY VIEW 3: CAREGIVER VERIFICATION CONSOLE */}
        {role === "ADMIN" && activeTab === "admin_verify" && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-lg font-extrabold text-slate-900">
              Caregiver Verification Console (Rule 5 Enforcement)
            </h3>
            <div className="divide-y divide-slate-100">
              {caregivers.map((cg) => (
                <div key={cg.id} className="py-3.5 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="font-bold text-slate-900">
                      {cg.full_name} <span className="text-xs font-normal text-slate-500">({cg.locality})</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      Status: <strong>{cg.verification_status}</strong> • Verified Badge:{" "}
                      <strong>{cg.is_verified_badge ? "YES" : "NO"}</strong>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleAdminVerifyCaregiver(cg.id, "VERIFIED")}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg"
                    >
                      Approve (VERIFIED)
                    </button>
                    <button
                      onClick={() => handleAdminVerifyCaregiver(cg.id, "REJECTED")}
                      className="bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold px-3 py-1.5 rounded-lg"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ADMIN ONLY VIEW 4: PLATFORM USERS */}
        {role === "ADMIN" && activeTab === "admin_users" && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-lg font-extrabold text-slate-900">
              Registered Platform Users ({allUsers.length})
            </h3>
            <div className="divide-y divide-slate-100">
              {allUsers.map((u) => (
                <div key={u.id} className="py-3 flex items-center justify-between text-sm">
                  <div>
                    <p className="font-bold text-slate-900">{u.full_name}</p>
                    <p className="text-xs text-slate-500">{u.email} • {u.phone || "No phone"}</p>
                  </div>
                  <span className="text-xs font-extrabold px-2.5 py-1 rounded-full bg-purple-50 text-purple-900">
                    {u.role}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* QUOTE & BOOKING MODAL */}
      {selectedCaregiver && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-lg font-extrabold text-slate-900">
                  Request Booking with {selectedCaregiver.full_name}
                </h3>
                <p className="text-xs text-slate-500">
                  Pet: {bruno?.name || "Bruno"} ({bruno?.media_gallery?.length || 0} Videos/Photos Attached for Admin Review)
                </p>
              </div>
              <button
                onClick={() => setSelectedCaregiver(null)}
                className="text-slate-400 hover:text-slate-700 font-bold text-lg"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-600 mb-1">Select Service</label>
                <select
                  value={bookingServiceType}
                  onChange={(e) => {
                    setBookingServiceType(e.target.value);
                    fetchQuote(selectedCaregiver.id, e.target.value, startDate, endDate);
                  }}
                  className="w-full text-sm border border-slate-300 rounded-xl px-3 py-2"
                >
                  {(selectedCaregiver.services || []).map((s: any) => (
                    <option key={s.id} value={s.service_type}>
                      {s.service_type.replace(/_/g, " ")} — ₹{s.price_inr} ({s.price_unit})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">Start Date &amp; Time</label>
                  <input
                    type="datetime-local"
                    value={startDate}
                    onChange={(e) => {
                      setStartDate(e.target.value);
                      fetchQuote(selectedCaregiver.id, bookingServiceType, e.target.value, endDate);
                    }}
                    className="w-full text-xs border border-slate-300 rounded-xl px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1">End Date &amp; Time</label>
                  <input
                    type="datetime-local"
                    value={endDate}
                    onChange={(e) => {
                      setEndDate(e.target.value);
                      fetchQuote(selectedCaregiver.id, bookingServiceType, startDate, e.target.value);
                    }}
                    className="w-full text-xs border border-slate-300 rounded-xl px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-600 mb-1">
                  Care Plan Instructions for Admin &amp; Caretaker
                </label>
                <textarea
                  rows={2}
                  value={specialInstructions}
                  onChange={(e) => setSpecialInstructions(e.target.value)}
                  className="w-full text-xs border border-slate-300 rounded-xl p-2.5"
                />
              </div>

              {quote && (
                <div className="bg-purple-50/70 border border-purple-100 rounded-xl p-3.5 text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-600">
                      ₹{quote.unit_price_inr} × {quote.units_count} {quote.price_unit.replace("PER_", "").toLowerCase()}(s)
                    </span>
                    <span className="font-bold text-slate-900">₹{quote.subtotal_inr}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setSelectedCaregiver(null)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateBooking}
                disabled={quote && !quote.is_available}
                className="bg-purple-700 hover:bg-purple-800 text-white text-sm font-bold px-5 py-2.5 rounded-xl shadow-sm"
              >
                Submit Booking &amp; Notify Admin
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
