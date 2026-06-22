package com.nanmuli.blog.application.file;

import com.nanmuli.blog.application.file.command.UploadFileCommand;
import com.nanmuli.blog.domain.file.FileRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

class FileAppServiceTest {

    private FileAppService service;

    @BeforeEach
    void setUp() {
        service = new FileAppService(mock(FileRepository.class), mock(ImageThumbnailService.class));
        ReflectionTestUtils.setField(service, "maxFileSize", 1024L);
        ReflectionTestUtils.setField(service, "allowedExtensionsConfig", "jpg, png, txt");
    }

    @Test
    void uploadRejectsPathLikeOriginalNameBeforeWritingFile() {
        UploadFileCommand command = command("../avatar.png", "image/png", new byte[]{1, 2, 3, 4});

        assertThatThrownBy(() -> service.upload(command))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    void uploadRejectsControlCharactersInOriginalName() {
        UploadFileCommand command = command("bad\nname.png", "image/png", new byte[]{1, 2, 3, 4});

        assertThatThrownBy(() -> service.upload(command))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    void uploadRejectsMissingContentAndSize() {
        UploadFileCommand command = command("avatar.png", "image/png", null);
        command.setFileSize(null);

        assertThatThrownBy(() -> service.upload(command))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    void uploadRejectsOversizedFile() {
        UploadFileCommand command = command("note.txt", "text/plain", new byte[1025]);

        assertThatThrownBy(() -> service.upload(command))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    void uploadRejectsImageWithMismatchedMagicNumber() {
        UploadFileCommand command = command("avatar.png", "image/png", new byte[]{1, 2, 3, 4});

        assertThatThrownBy(() -> service.upload(command))
                .isInstanceOf(BusinessException.class);
    }

    private UploadFileCommand command(String name, String contentType, byte[] content) {
        UploadFileCommand command = new UploadFileCommand();
        command.setOriginalName(name);
        command.setContentType(contentType);
        command.setContent(content);
        command.setFileSize(content == null ? 0L : (long) content.length);
        return command;
    }
}
