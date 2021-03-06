import collections
import datetime
import functools
import urllib.parse

from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy
from django.db import models
from django.utils.timezone import make_naive
from django.utils.translation import ugettext, ugettext_lazy as _

from core.models import BigForeignKey, EventInfo
from core.utils import format_html_lazy
from proposals.models import TalkProposal


DAY_1 = datetime.date(2016, 6, 3)
DAY_2 = datetime.date(2016, 6, 4)
DAY_3 = datetime.date(2016, 6, 5)
DAY_NAMES = collections.OrderedDict([
    (DAY_1, _('Day 1')),
    (DAY_2, _('Day 2')),
    (DAY_3, _('Day 3')),
])


class TimeManager(models.Manager):
    def get(self, value):
        """We only has one field, so let's make it available without keyword.
        """
        return super().get(value=value)


@functools.total_ordering
class Time(models.Model):

    value = models.DateTimeField(
        primary_key=True,
        verbose_name=_('value'),
    )

    objects = TimeManager()

    class Meta:
        verbose_name = _('time')
        verbose_name_plural = _('times')
        ordering = ['value']

    def __str__(self):
        return str(make_naive(self.value))

    def __lt__(self, other):
        if not isinstance(other, Time):
            return NotImplemented
        if (not isinstance(self.value, datetime.datetime) or
                not isinstance(other.value, datetime.datetime)):
            return NotImplemented
        return self.value < other.value


class Location:
    """All possible location combinations.

    The numbering prefix helps to order events by locations. We need this
    information when resolving events in the same time period.

    Rules:

    1. The R3 events are put first.
    2. Belt and partial belt events are next, in that order.
    3. Block events in R0-2 are next, in that order.
    """
    R3   = '1-r3'
    ALL  = '2-all'
    R012 = '3-r012'
    R0   = '4-r0'
    R1   = '5-r1'
    R2   = '6-r2'

    @classmethod
    def get_md_width(cls, value):
        return {
            '2-all': 4,
            '3-r012': 3,
            '4-r0': 1,
            '5-r1': 1,
            '6-r2': 1,
            '1-r3': 1,
        }[value]


class BaseEvent(models.Model):
    """Base interface for all events in the schedule.
    """
    LOCATION_CHOICES = [
        (Location.ALL,  _('All rooms')),
        (Location.R012, _('R0, R1, R2')),
        (Location.R0,   _('R0')),
        (Location.R1,   _('R1')),
        (Location.R2,   _('R2')),
        (Location.R3,   _('R3')),
    ]
    location = models.CharField(
        max_length=6,
        choices=LOCATION_CHOICES,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('location'),
    )

    begin_time = models.ForeignKey(
        to=Time,
        blank=True,
        null=True,
        related_name='begined_%(class)s_set',
        verbose_name=_('begin time'),
    )

    end_time = models.ForeignKey(
        to=Time,
        blank=True,
        null=True,
        related_name='ended_%(class)s_set',
        verbose_name=_('end time'),
    )

    class Meta:
        abstract = True


class CustomEvent(BaseEvent):

    title = models.CharField(
        max_length=140,
        verbose_name=_('title'),
    )

    class Meta:
        verbose_name = _('custom event')
        verbose_name_plural = _('custom events')

    def __str__(self):
        return self.title


class KeynoteEvent(BaseEvent):

    speaker_name = models.CharField(
        verbose_name=_('speaker name'),
        max_length=100,
    )
    slug = models.SlugField(
        verbose_name=_('slug'),
        help_text=format_html_lazy(
            _("This is used to link to the speaker's introduction on the "
              "Keynote page, e.g. 'liang2' will link to "
              "'{link}#keynote-speaker-liang2'."),
            link=reverse_lazy('page', kwargs={'path': 'events/keynotes'}),
        )
    )

    class Meta:
        verbose_name = _('keynote event')
        verbose_name_plural = _('keynote events')

    def __str__(self):
        return ugettext('Keynote: {speaker}'.format(
            speaker=self.speaker_name,
        ))

    def get_absolute_url(self):
        url = reverse('page', kwargs={'path': 'events/keynotes'})
        split = urllib.parse.urlsplit(url)
        frag = 'keynote-speaker-{slug}'.format(slug=self.slug)
        return urllib.parse.urlunsplit(split._replace(fragment=frag))


class SponsoredEvent(EventInfo, BaseEvent):

    host = BigForeignKey(
        to=settings.AUTH_USER_MODEL,
        verbose_name=_('host'),
    )
    slug = models.SlugField(
        allow_unicode=True,
        verbose_name=_('slug'),
    )

    class Meta:
        verbose_name = _('sponsored event')
        verbose_name_plural = _('sponsored events')

    def get_absolute_url(self):
        return reverse('events_sponsored_event_detail', kwargs={
            'slug': self.slug,
        })


class ProposedTalkEventManager(models.Manager):
    def get_queryset(self):
        """We almost always need the proposal info, so let's always JOIN it.
        """
        return super().get_queryset().select_related('proposal')


class ProposedTalkEvent(BaseEvent):

    proposal = BigForeignKey(
        to=TalkProposal,
        limit_choices_to={'accepted': True},
        verbose_name=_('proposal'),
    )

    objects = ProposedTalkEventManager()

    class Meta:
        verbose_name = _('talk event')
        verbose_name_plural = _('talk events')

    def __str__(self):
        return self.proposal.title

    def get_absolute_url(self):
        return reverse('events_talk_detail', kwargs={'pk': self.proposal.pk})


class Schedule(models.Model):

    html = models.TextField(
        verbose_name=_('HTML'),
    )
    created_at = models.DateTimeField(
        verbose_name=_('created at'),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _('Schedule')
        verbose_name_plural = _('Schedules')
        ordering = ['-created_at']
        get_latest_by = 'created_at'

    def __str__(self):
        return ugettext('Schedule created at {}').format(self.created_at)
