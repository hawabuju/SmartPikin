import os
import markdown
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
import pdfkit
from groq import Groq

from core.models import CreativeWritingPrompt
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Configure Groq client
groq_client = Groq(api_key=settings.GROQ_API_KEY)


# class CreativeWritingAssistantView(View):
#     template_name = 'ai_core/creative_writing_assistant.html'
#
#     def get(self, request):
#         return render(request, self.template_name)
#
#     def post(self, request):
#         # Get form inputs
#         genre = request.POST.get('genre')
#         tone = request.POST.get('tone')
#         level = request.POST.get('level')
#         location = request.POST.get('location')
#         theme = request.POST.get('theme')
#         plot = request.POST.get('plot')
#         idea = request.POST.get('idea')
#         title = request.POST.get('title')
#
#         # Validate user input
#         if not all([genre, tone, level, location, theme, plot, idea, title]):
#             messages.error(request, "Please fill out all fields.")
#             return render(request, self.template_name)
#
#         # Generate the creative writing prompt using the Google Gemini API
#         prompt_data = self.generate_creative_writing_prompt(genre, tone, level, location, theme, plot, idea, title)
#
#         # Check if a prompt was successfully generated
#         if prompt_data:
#             # Convert Markdown to HTML
#             prompt_html = markdown.markdown(prompt_data['prompt'])
#
#             # Save the creative writing prompt to the database
#             saved_prompt = CreativeWritingPrompt.objects.create(
#                 user=request.user,
#                 genre=genre,
#                 tone=tone,
#                 level=level,
#                 location=location,
#                 theme=theme,
#                 plot=plot,
#                 idea=idea,
#                 title=title,
#                 prompt=prompt_html
#             )
#             return render(request, self.template_name, {
#                 'genre': genre,
#                 'tone': tone,
#                 'level': level,
#                 'location': location,
#                 'theme': theme,
#                 'plot': plot,
#                 'idea': idea,
#                 'title': title,
#                 'writing_prompt': prompt_html,
#                 'writing_prompt_id': saved_prompt.id
#             })
#         else:
#             messages.error(request, "Failed to generate creative writing prompt. Please try again.")
#             return render(request, self.template_name)
#
#     def generate_creative_writing_prompt(self, genre, tone, level, location, theme, plot, idea, title):
#         """Generate a creative writing prompt using Google Gemini API, tailored for Sierra Leone's context."""
#         try:
#             # Initialize the model
#             model = genai.GenerativeModel("gemini-2.0-flash")
#
#             # Generate culturally relevant content
#             prompt = (
#                 f"Write a captivating and uplifting essay in the genre of '{genre}', with a '{tone}' tone, "
#                 f"tailored for students at the '{level}' level in Sierra Leone, focusing on the area of {location}. "
#                 f"The essay should have the following structure and elements:\n\n"
#
#                 f"1. Title: Create a title for the story that is compelling and immediately piques curiosity. "
#                 f"The title should reflect the theme '{theme}' and be irresistible to readers.\n\n"
#
#                 f"2. Opening Paragraph: Begin with a powerful opening sentence or question to captivate the reader. "
#                 f"Introduce the theme of the story, '{theme}', in a way that hooks readers into the story's setting and mood.\n\n"
#
#                 f"3. Body Paragraphs: Develop the plot over three paragraphs. Each paragraph should build on the story’s main idea, '{idea}', "
#                 f"and incorporate the plot point '{plot}' while subtly showcasing aspects of Sierra Leone's culture, daily life, and natural beauty. "
#                 f"Highlight local experiences, such as vibrant markets, beautiful landscapes, or community gatherings.\n\n"
#
#                 f"4. Cultural Touch: Include a Krio expression or quote, 'Afta de rain, na de sun we go feel,' to add authenticity "
#                 f"and cultural depth to the story, providing readers with a sense of identity and pride.\n\n"
#
#                 f"5. Character Development: Offer tips for developing relatable characters with clear personalities. "
#                 f"Include simple descriptions that help students envision characters in everyday situations.\n\n"
#
#                 f"6. Setting & Imagery: Use vivid, relatable descriptions of Sierra Leonean settings that allow readers to feel "
#                 f"immersed in the story’s environment. Include sensory details to make scenes feel alive.\n\n"
#
#                 f"7. Closing Paragraph: End with a strong, positive conclusion that reinforces the story's central idea "
#                 f"and leaves readers feeling inspired and hopeful, in line with the tone '{tone}'.\n\n"
#
#                 f"8. Language & Tone: Use simple, accessible language appropriate for {level} students. "
#                 f"The tone should emphasize resilience, hope, and the joys of creativity in storytelling.\n\n"
#
#                 f"9. Length: Ensure the essay falls within 500-900 words, offering a complete story experience.\n\n"
#
#                 f"10. Tips on Writing: Throughout, integrate engaging, easy-to-follow tips on character development, plot structure, "
#                 f"and setting creation to help students enhance their writing skills in an enjoyable way."
#             )
#
#             # Generate content using the model
#             response = model.generate_content(prompt)
#             return {"prompt": response.text}
#         except Exception as e:
#             logger.error(f"Error generating content: {e}")
#             return None


class CreativeWritingAssistantView(LoginRequiredMixin, View):
    template_name = 'ai_core/creative_writing_assistant.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # Gather initial or follow-up form inputs
        genre = request.POST.get('genre')
        tone = request.POST.get('tone')
        level = request.POST.get('level')
        location = request.POST.get('location')
        theme = request.POST.get('theme')
        plot = request.POST.get('plot')
        idea = request.POST.get('idea')
        title = request.POST.get('title')

        # Identify if this is a follow-up request
        follow_up_request = request.POST.get('follow_up_request')
        writing_prompt_id = request.POST.get('writing_prompt_id')

        if follow_up_request and writing_prompt_id:
            # Handle follow-up content generation
            writing_prompt = get_object_or_404(CreativeWritingPrompt, id=writing_prompt_id, user=request.user)
            follow_up_content = self.generate_follow_up_content(
                writing_prompt.genre, writing_prompt.tone, writing_prompt.level,
                writing_prompt.location, writing_prompt.theme, writing_prompt.plot,
                writing_prompt.idea, follow_up_request
            )

            follow_up_content_html = markdown.markdown(follow_up_content)
            combined_content = writing_prompt.prompt + follow_up_content_html
            writing_prompt.prompt = combined_content
            writing_prompt.save()

            return render(request, self.template_name, {
                'genre': writing_prompt.genre,
                'tone': writing_prompt.tone,
                'level': writing_prompt.level,
                'location': writing_prompt.location,
                'theme': writing_prompt.theme,
                'plot': writing_prompt.plot,
                'idea': writing_prompt.idea,
                'title': writing_prompt.title,
                'writing_prompt': combined_content,
                'writing_prompt_id': writing_prompt.id,
                'follow_up_content': follow_up_content_html,
            })

        # Original creative writing generation
        if not all([genre, tone, level, location, theme, plot, idea, title]):
            messages.error(request, "Please fill out all fields.")
            return render(request, self.template_name)

        prompt_data = self.generate_creative_writing_prompt(genre, tone, level, location, theme, plot, idea, title)

        if prompt_data:
            prompt_html = markdown.markdown(prompt_data['prompt'])
            saved_prompt = CreativeWritingPrompt.objects.create(
                user=request.user, genre=genre, tone=tone, level=level,
                location=location, theme=theme, plot=plot, idea=idea,
                title=title, prompt=prompt_html
            )

            return render(request, self.template_name, {
                'genre': genre,
                'tone': tone,
                'level': level,
                'location': location,
                'theme': theme,
                'plot': plot,
                'idea': idea,
                'title': title,
                'writing_prompt': prompt_html,
                'writing_prompt_id': saved_prompt.id,
                'prompt_improvement_tips': prompt_data['improvement_tips'],

            })
        else:
            messages.error(request, "Failed to generate creative writing prompt. Please try again.")
            return render(request, self.template_name)

    def generate_creative_writing_prompt(self, genre, tone, level, location, theme, plot, idea, title):
        """Generate a creative writing prompt using Groq API, with guidance tips."""
        try:
            prompt = (
                f"Write a captivating story in the '{genre}' genre with a '{tone}' tone for '{level}' level readers in Sierra Leone. "
                f"Ensure the story highlights aspects of '{theme}' and has a relatable plot '{plot}' while staying culturally relevant to Sierra Leone. "
                f"Structure the story as follows:\n\n"
                f"1. **Title:** Start with a compelling title reflecting the theme '{theme}'.\n\n"
                f"2. **Opening Paragraph:** Begin with an engaging sentence that sets the mood.\n\n"
                f"3. **Body Paragraphs:** Develop the story across three paragraphs. Include descriptions "
                f"of Sierra Leonean culture, landscapes, and experiences, making it feel authentic and local.\n\n"
                f"4. **Conclusion:** Conclude with a message of resilience or joy, as fits the '{tone}'.\n\n"
                f"5. **Character Tips:** Add characters that readers can relate to, using easy, memorable descriptions.\n\n"
                f"6. **Setting & Imagery:** Paint a vivid image of the setting that draws readers in.\n\n"
                f"7. **Story Length:** Keep it within 500-900 words.\n\n"
                f"8. **Writing Tips:** Add simple pointers to help writers improve their story structure, "
                f"like focusing on plot progression and character development.\n\n"
            )

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            improvement_tips = (
                "Consider asking follow-up questions to clarify the direction of the story, such as:\n"
                "1. How can character backgrounds be enhanced?\n"
                "2. What additional cultural details could make the setting more vivid?\n"
                "3. How can the story's theme be emphasized more effectively?"
            )

            return {"prompt": response.choices[0].message.content, "improvement_tips": improvement_tips}

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return None

    def generate_follow_up_content(self, genre, tone, level, location, theme, plot, idea, follow_up_request):
        """Generate follow-up content based on user feedback."""
        try:
            prompt = (
                f"Based on a '{genre}' story for '{level}' readers in Sierra Leone, following the theme '{theme}' "
                f"and plot '{plot}', provide enhancements based on this feedback: {follow_up_request}. "
                f"Keep the content culturally resonant and user-friendly."
            )

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating follow-up content: {e}")
            return None


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.http import HttpResponse
import pdfkit
import datetime


@login_required
def download_writing_prompt_pdf(request, id):
    """Generate and download the writing prompt as a PDF."""
    writing_prompt = get_object_or_404(CreativeWritingPrompt, id=id, user=request.user)

    if not writing_prompt.prompt:
        messages.error(request, "No writing prompt available to download.")
        return redirect('ai_core:creative_writing_assistant')

    # Resolve static path for the logo
    logo_url = request.build_absolute_uri(static('core/images/header_logo.png'))

    # Render HTML with Django template
    writing_prompt_html = render_to_string(
        'ai_core/writing_prompt_pdf.html',
        {
            'writing_prompt_content': writing_prompt.prompt,
            'generated_date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'logo_url': logo_url,  # Pass the full logo URL to the template
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
        "footer-left": "Creative Writing Prompt",
        "footer-font-size": "10",
        "header-font-size": "10",
        "print-media-type": None,
        "minimum-font-size": 12,
        "disable-smart-shrinking": None,
    }

    # Generate and return PDF response
    pdf = pdfkit.from_string(writing_prompt_html, False, options=options)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="creative_writing_prompt.pdf"'
    return response


from django.views.generic import ListView
from core.models import CreativeWritingPrompt


class CreativeWritingPromptListView(LoginRequiredMixin, ListView):
    model = CreativeWritingPrompt
    template_name = 'ai_core/creative_writing_prompt_list.html'  # The template for displaying the list
    context_object_name = 'creative_writing_prompts'

    def get_queryset(self):
        # Only return creative writing prompts created by the current user
        return CreativeWritingPrompt.objects.filter(user=self.request.user).order_by('-created_at')
