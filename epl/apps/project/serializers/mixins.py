from epl.apps.project.models import Collection, Resource
from epl.apps.project.models.collection import TurnType
from epl.apps.user.models import User


class ResourceInstructionMixin:
    """Mixin to add resource instruction/positioning checks to serializers"""

    def get_should_instruct(self, obj) -> bool:
        # obj can be either a Resource or a Collection
        resource = obj if isinstance(obj, Resource) else obj.resource
        next_turn: TurnType | None = resource.next_turn
        library_id = next_turn["library"] if next_turn else None
        user: User = self.context.get("request").user

        if not user or not user.is_authenticated or not library_id:
            return False
        return user.is_instructor(resource.project, library_id)

    def get_should_position(self, obj) -> bool:
        # obj can be either a Resource or a Collection
        resource = obj if isinstance(obj, Resource) else obj.resource
        user: User = self.context.get("request").user
        library_id_selected = self.context.get("library") if isinstance(obj, Resource) else obj.library.id

        if (
            library_id_selected
            and user.is_authenticated
            and user.is_instructor(project=resource.project, library=library_id_selected)
        ):
            return Collection.objects.filter(
                resource=resource, library_id=library_id_selected, position=None, exclusion_reason__in=["", None]
            ).exists()

        return False
