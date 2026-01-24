class Person:
    def __init__(self, name, role, family, parent=None):
        self.name = name
        self.role = role
        self.family = family
        self.parent = parent  # New: Parent reference (optional)
        family.add_member(self)

    def __str__(self):
        return f"{self.name} ({self.role})"

    def get_relationship(self, other_person):
        if self.family == other_person.family:
            if self.role == "parent" and other_person.role == "child":
                return f"{other_person.name} is the child of {self.name}."
            elif self.role == "child" and other_person.role == "parent":
                return f"{other_person.name} is the parent of {self.name}."
            elif self.role == "sibling" and other_person.role == "sibling":
                return f"{self.name} and {other_person.name} are siblings."
            else:
                return f"{self.name} and {other_person.name} have no direct relationship."
        else:
            return f"{self.name} and {other_person.name} are from different families."

    # New: Function to get child members (for family tree generation)
    def get_children(self):
        children = []
        for member in self.family.members:
            if member.parent == self:
                children.append(member)
        return children

class Family:
    def __init__(self, name):
        self.name = name
        self.members = []

    def add_member(self, person):
        self.members.append(person)

    def display_family(self):
        print(f"Family: {self.name}")
        for member in self.members:
            print(f"  - {member}")

    # New: Function to print the family tree (parent -> child hierarchy)
    def generate_family_tree(self):
        for member in self.members:
            if member.role == "parent":  # Only parents have children
                print(f"{member.name} (Parent) -> ", end="")
                children = member.get_children()
                if children:
                    print(", ".join([child.name for child in children]))
                else:
                    print("No children")

# Example usage:
# Create two families
family_a = Family("Smith")
family_b = Family("Johnson")

# Create members for family A
father = Person("John Smith", "parent", family_a)
mother = Person("Jane Smith", "parent", family_a)
child = Person("Alex Smith", "child", family_a, parent=father)
sibling = Person("Alice Smith", "child", family_a, parent=father)

# Create members for family B
other_parent = Person("Michael Johnson", "parent", family_b)
other_child = Person("Emily Johnson", "child", family_b, parent=other_parent)

# Display families
family_a.display_family()
family_b.display_family()

# Generate family tree for each family
print("\nFamily Tree for Smith family:")
family_a.generate_family_tree()

print("\nFamily Tree for Johnson family:")
family_b.generate_family_tree()

# Test relationships
print(father.get_relationship(child))  # John Smith is the parent of Alex Smith.
print(sibling.get_relationship(child))  # Alice Smith and Alex Smith are siblings.
print(child.get_relationship(other_child))  # Alex Smith and Emily Johnson are from different families.