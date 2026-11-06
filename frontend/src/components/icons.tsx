import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

function base(paths: string[]) {
  return function Icon(props: IconProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        {...props}
      >
        {paths.map((d) => (
          <path key={d} d={d} />
        ))}
      </svg>
    )
  }
}

export const IconDashboard = base(['M4 13h6V4H4z', 'M14 20h6v-9h-6z', 'M4 20h6v-3H4z', 'M14 7h6V4h-6z'])
export const IconCheck = base(['M9 11l3 3 8-8', 'M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9'])
export const IconOrg = base(['M10 3h4v4h-4z', 'M3 17h4v4H3z', 'M10 17h4v4h-4z', 'M17 17h4v4h-4z', 'M12 7v5', 'M5 17v-2.5h14V17', 'M12 12v5'])
export const IconUsers = base([
  'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
  'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  'M22 21v-2a4 4 0 0 0-3-3.87',
  'M16 3.13a4 4 0 0 1 0 7.75',
])
export const IconClock = base(['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'M12 6v6l4 2'])
export const IconCalendar = base(['M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M16 2v4', 'M8 2v4', 'M3 10h18'])
export const IconWallet = base(['M20 7H5a2 2 0 0 1 0-4h13v4', 'M3 5v14a2 2 0 0 0 2 2h15V7', 'M16 14h.01'])
export const IconBriefcase = base(['M4 7h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z', 'M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2', 'M3 13h18'])
export const IconChart = base(['M3 3v18h18', 'M7 15l4-4 3 3 5-6'])
export const IconSettings = base([
  'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
])
export const IconHome = base(['M3 10.5L12 3l9 7.5', 'M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5'])
export const IconReceipt = base(['M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2z', 'M9 8h6', 'M9 12h6', 'M9 16h3'])
export const IconUser = base(['M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2', 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z'])
export const IconSun = base([
  'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z',
  'M12 1v2',
  'M12 21v2',
  'M4.22 4.22l1.42 1.42',
  'M18.36 18.36l1.42 1.42',
  'M1 12h2',
  'M21 12h2',
  'M4.22 19.78l1.42-1.42',
  'M18.36 5.64l1.42-1.42',
])
export const IconMoon = base(['M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z'])
export const IconLogout = base(['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'M16 17l5-5-5-5', 'M21 12H9'])
export const IconMenu = base(['M4 6h16', 'M4 12h16', 'M4 18h16'])
export const IconX = base(['M18 6L6 18', 'M6 6l12 12'])
export const IconSearch = base(['M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z', 'M21 21l-4.35-4.35'])
export const IconSwap = base(['M7 16V4', 'M3 8l4-4 4 4', 'M17 8v12', 'M21 16l-4 4-4-4'])
export const IconInbox = base(['M22 12h-6l-2 3h-4l-2-3H2', 'M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z'])
