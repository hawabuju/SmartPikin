from django.conf import settings
from django.core.files.storage import FileSystemStorage
from formtools.wizard.views import SessionWizardView
from core.forms import BasicInfoForm, SchoolLevelForm, ParentContactForm, AdditionalInfoForm
from account.mixins import UserIsGuardianMixin


# Define the steps in the form wizard
FORMS = [
    ('basic_info', BasicInfoForm),
    ('school_level', SchoolLevelForm),
    ('parent_contact', ParentContactForm),
    ('additional_info', AdditionalInfoForm),
]

TEMPLATES = {
    'basic_info': 'application/basic_info.html',
    'school_level': 'application/school_level.html',
    'parent_contact': 'application/parent_contact.html',
    'additional_info': 'application/additional_info.html',
}

from django.shortcuts import render, get_object_or_404
from core.models import Application, School


class ApplicationFormWizard(SessionWizardView, UserIsGuardianMixin):
    form_list = [BasicInfoForm, SchoolLevelForm, ParentContactForm, AdditionalInfoForm]
    template_name = 'application/wizard_form.html'
    file_storage = FileSystemStorage(location=settings.MEDIA_ROOT)

    def get_form_kwargs(self, step):
        kwargs = super().get_form_kwargs(step)
        school_pk = self.kwargs.get('pk')
        school = get_object_or_404(School, pk=school_pk)
        kwargs.update({'user': self.request.user})
        if step in ['basic_info', 'school_level', 'parent_contact', 'additional_info']:
            kwargs.update({'school': school})
        return kwargs

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        school_pk = self.kwargs.get('pk')
        context['school'] = get_object_or_404(School, pk=school_pk)
        return context

    def done(self, form_list, **kwargs):
        application_data = {}
        for form in form_list:
            application_data.update(form.cleaned_data)

        user = self.request.user
        school = get_object_or_404(School, pk=self.kwargs.get('pk'))

        # Create the application instance and save it
        application = Application.objects.create(user=user, school=school, **application_data)

        # Manually trigger the save method to generate application_code and qr_code
        application.save()

        return render(self.request, 'application/application_done.html', {'application': application})


import base64
from io import BytesIO
from django.core.files.storage import default_storage


def encode_image(image_field):
    if not image_field:
        return None
    file = default_storage.open(image_field.name)
    return f"data:image/png;base64,{base64.b64encode(file.read()).decode()}"


from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
import pdfkit
import datetime


def download_application(request, application_id):
    """Generate and download the application as a PDF."""
    # Fetch the application associated with the user
    application = get_object_or_404(Application, pk=application_id, user=request.user)

    # Resolve static path for the logo (if needed)
    logo_url = request.build_absolute_uri(static('core/images/header_logo.png'))

    # Render HTML using a Django template
    application_html = render_to_string(
        'application/application_pdf.html',
        {
            'application': application,
            'generated_date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'logo_url': logo_url,  # Pass the logo URL to the template
            'application_image_base64': encode_image(application.applicant_image),
            'qr_code_base64': encode_image(application.qr_code),
        }
    )

    # PDF options for optimal rendering
    options = {
        "enable-local-file-access": "",
        "page-size": "A4",
        "margin-top": "1in",
        "margin-right": "1in",
        "margin-bottom": "1in",
        "margin-left": "1in",
        "encoding": "UTF-8",
        "dpi": 300,
        "orientation": "Portrait",
        "zoom": "1.1",
        "footer-right": "[page] of [topage]",
        "header-left": f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d')}",
        "footer-left": "Application Details",
        "footer-font-size": "10",
        "header-font-size": "10",
        "print-media-type": None,
        "minimum-font-size": 12,
        "disable-smart-shrinking": None,
    }

    # Generate PDF from HTML
    pdf = pdfkit.from_string(application_html, False, options=options)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="application_{application.application_code}.pdf"'
    return response
