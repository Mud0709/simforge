"""The pure physics of A2 (momentum, collisions, impulse, explosions), written by the author.

What this file is: the "core" of the module. Each function takes plain numbers and
returns plain numbers. No web framework, no files, no random numbers; just physics.

Units are SI: mass in kg, velocity in m/s, momentum in kg m/s, energy in J, force in N,
time in s. In 1-D a velocity is a signed number: the sign is the direction.

Who writes what: the author writes every function body here, sitting by sitting
(see docs/FOUNDATIONS_CODING_GUIDE.md). The stubs below only fix the names, the
arguments and what each function means; until you write one it raises NotImplementedError.
"""


def momentum(m: float, v: float) -> float:
    """Momentum of one body, in kg m/s: its mass (kg) times its velocity (m/s).

    The sign of v gives the direction (positive one way, negative the other)."""
    raise NotImplementedError(
        "Sitting 0: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 9."
    )


def kinetic_energy(m: float, v: float) -> float:
    """Kinetic energy of one body, in joules: the energy it has because it moves.

    m is the mass (kg), v the velocity (m/s). Energy is never negative,
    whichever way the body moves."""
    raise NotImplementedError(
        "Sitting 1: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 9."
    )


def total_momentum(m1: float, v1: float, m2: float, v2: float) -> float:
    """Total momentum of two bodies, in kg m/s: the sum of their momenta.

    Masses m1, m2 in kg; velocities v1, v2 in m/s (sign = direction)."""
    raise NotImplementedError(
        "Sitting 1: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 9."
    )


def total_kinetic_energy(m1: float, v1: float, m2: float, v2: float) -> float:
    """Total kinetic energy of two bodies, in joules: the sum of their kinetic energies.

    Masses m1, m2 in kg; velocities v1, v2 in m/s."""
    raise NotImplementedError(
        "Sitting 1: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 9."
    )


def centre_of_mass_velocity(m1: float, v1: float, m2: float, v2: float) -> float:
    """Velocity of the centre of mass of two bodies, in m/s.

    It is the single velocity at which the pair's total momentum would be
    carried if both bodies had moved together as one. Masses in kg,
    velocities in m/s."""
    raise NotImplementedError(
        "Sitting 1: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 9."
    )


def collide_1d(m1: float, m2: float, u1: float, u2: float, e: float) -> tuple[float, float]:
    """Two bodies collide head-on along a line; return their velocities after, (v1, v2), in m/s.

    m1, m2: masses (kg). u1, u2: velocities before (m/s). e: coefficient of
    restitution, how much of the approach speed comes back as separation
    speed (0 = they stick together, 1 = perfectly elastic). Momentum is
    conserved for every e."""
    raise NotImplementedError(
        "Sitting 2: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 10."
    )


def impulse(m: float, u: float, v: float) -> float:
    """Impulse on one body, in N s: the change in that body's momentum.

    m is the mass (kg), u the velocity before and v the velocity after (m/s)."""
    raise NotImplementedError(
        "Sitting 3: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 11."
    )


def average_force(j: float, dt: float) -> float:
    """Average force, in newtons, that delivers an impulse j (N s) over a contact time dt (s)."""
    raise NotImplementedError(
        "Sitting 3: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 11."
    )


def explosion_velocity(m1: float, m2: float, u: float, v1: float) -> float:
    """Velocity (m/s) of piece 2 after a body at velocity u splits into pieces 1 and 2.

    m1, m2: piece masses (kg). u: velocity before the split (m/s). v1: velocity
    of piece 1 after (m/s). No outside force acts, so total momentum is unchanged."""
    raise NotImplementedError(
        "Sitting 3: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 11."
    )


def energy_released(m1: float, m2: float, u: float, v1: float, v2: float) -> float:
    """Energy released by an explosion, in joules.

    m1, m2: piece masses (kg). u: velocity before (m/s). v1, v2: velocities of
    the pieces after (m/s). It is the kinetic energy gained by the system."""
    raise NotImplementedError(
        "Sitting 3: you write this function. See docs/FOUNDATIONS_CODING_GUIDE.md, chapter 11."
    )
