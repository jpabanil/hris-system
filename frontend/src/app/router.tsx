import { createBrowserRouter, Navigate } from 'react-router-dom'
import { HomeRedirect, RequireAuth } from './gates.tsx'
import { AdminShell } from '../layouts/admin-shell.tsx'
import { PortalShell } from '../layouts/portal-shell.tsx'
import { LoginPage } from '../routes/login-page.tsx'
import { ApprovalsPage } from '../routes/admin/approvals-page.tsx'
import { AttendancePage } from '../routes/admin/attendance-page.tsx'
import { DashboardPage } from '../routes/admin/dashboard-page.tsx'
import { EmployeeProfilePage } from '../routes/admin/employee-profile-page.tsx'
import { EmployeesPage } from '../routes/admin/employees-page.tsx'
import { LeavePage } from '../routes/admin/leave-page.tsx'
import { OrgPage } from '../routes/admin/org-page.tsx'
import { PayrollPage } from '../routes/admin/payroll-page.tsx'
import { RecruitmentPage } from '../routes/admin/recruitment-page.tsx'
import { ReportsPage } from '../routes/admin/reports-page.tsx'
import { SettingsPage } from '../routes/admin/settings-page.tsx'
import { PortalHomePage } from '../routes/portal/home-page.tsx'
import { PortalLeavePage } from '../routes/portal/leave-page.tsx'
import { PortalPayslipsPage } from '../routes/portal/payslips-page.tsx'
import { PortalProfilePage } from '../routes/portal/profile-page.tsx'
import { CareersPage } from '../routes/public/careers-page.tsx'
import { VerifyPage } from '../routes/public/verify-page.tsx'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/careers/:slug', element: <CareersPage /> },
  { path: '/verify/:code', element: <VerifyPage /> },
  {
    element: <RequireAuth />,
    children: [
      { index: true, element: <HomeRedirect /> },
      {
        path: 'admin',
        element: <AdminShell />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'approvals', element: <ApprovalsPage /> },
          { path: 'org', element: <OrgPage /> },
          { path: 'employees', element: <EmployeesPage /> },
          { path: 'employees/:id', element: <EmployeeProfilePage /> },
          { path: 'attendance', element: <AttendancePage /> },
          { path: 'leave', element: <LeavePage /> },
          { path: 'payroll', element: <PayrollPage /> },
          { path: 'recruitment', element: <RecruitmentPage /> },
          { path: 'reports', element: <ReportsPage /> },
          { path: 'settings', element: <SettingsPage /> },
        ],
      },
      {
        path: 'portal',
        element: <PortalShell />,
        children: [
          { index: true, element: <PortalHomePage /> },
          { path: 'leave', element: <PortalLeavePage /> },
          { path: 'payslips', element: <PortalPayslipsPage /> },
          { path: 'profile', element: <PortalProfilePage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
